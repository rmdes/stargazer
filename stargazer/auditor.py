import json
from pathlib import Path

import anthropic
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table

from stargazer.rate_limiter import RateLimiter
from stargazer.taxonomy import TaxonomyManager

DATA_DIR = Path("data")
CLASSIFICATIONS_FILE = DATA_DIR / "classifications.json"

console = Console()

AUDIT_PROMPT = """Review these GitHub repositories with their current classifications.
For each repo, determine if the current primary category is the best fit.

Taxonomy (valid category slugs):
{taxonomy}

Repositories with current classifications:

{repos}

For each repo, return:
- "correct": true if the current classification is the best fit
- "correct": false if a better category exists — provide "suggested_primary" and "reason"
- Be conservative: only flag genuinely wrong classifications

Return ONLY valid JSON (no markdown, no explanation):
{{
  "audits": [
    {{"full_name": "owner/repo", "correct": true}},
    {{"full_name": "owner/repo", "correct": false, "suggested_primary": "slug", "reason": "brief reason"}}
  ]
}}"""


class Auditor:
    def __init__(self, api_key: str, taxonomy: dict, batch_size: int = 20, delay: float = 2.0):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.taxonomy = taxonomy
        self.batch_size = batch_size
        self.limiter = RateLimiter(min_delay=delay)

    def audit_repos(self, repos: list[dict], classifications: dict[str, dict]) -> list[dict]:
        """Audit repos in batches, return list of disagreements."""
        batches = [repos[i:i + self.batch_size] for i in range(0, len(repos), self.batch_size)]
        disagreements = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
        ) as progress:
            task = progress.add_task("Auditing classifications...", total=len(repos))

            for batch in batches:
                self.limiter.wait()
                prompt = self._build_audit_prompt(batch, classifications)
                response = self._call_claude(prompt)
                results = self._parse_audit_response(response)

                for result in results:
                    result["current_primary"] = classifications.get(
                        result["full_name"], {}
                    ).get("primary", "unknown")
                    disagreements.append(result)

                progress.advance(task, advance=len(batch))

        return disagreements

    def _build_audit_prompt(self, repos: list[dict], classifications: dict[str, dict]) -> str:
        mgr = TaxonomyManager(self.taxonomy)
        slugs = sorted(mgr.all_slugs())
        taxonomy_str = ", ".join(slugs)

        lines = []
        for r in repos:
            cls = classifications.get(r["full_name"], {})
            primary = cls.get("primary", "unknown")
            base = TaxonomyManager.format_repo_for_prompt(r)
            lines.append(f"{base} | current: {primary}")

        return AUDIT_PROMPT.format(taxonomy=taxonomy_str, repos="\n".join(lines))

    def _call_claude(self, prompt: str) -> str:
        message = self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    @staticmethod
    def _parse_audit_response(text: str) -> list[dict]:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        data = json.loads(text)
        return [a for a in data["audits"] if not a.get("correct", True)]


def review_disagreements(
    disagreements: list[dict],
    classifications: dict[str, dict],
    auto_accept: bool = False,
) -> int:
    """Interactive review of audit disagreements. Returns count of accepted changes."""
    if not disagreements:
        console.print("[green]No disagreements found — all classifications look correct![/]")
        return 0

    console.print(f"\n[bold]Found {len(disagreements)} potential misclassification(s)[/]\n")

    accepted = 0
    for i, d in enumerate(disagreements, 1):
        table = Table(title=f"[{i}/{len(disagreements)}] {d['full_name']}", show_header=False)
        table.add_column("Field", style="bold")
        table.add_column("Value")
        table.add_row("Current", d.get("current_primary", "unknown"))
        table.add_row("Suggested", d.get("suggested_primary", "?"))
        table.add_row("Reason", d.get("reason", ""))
        console.print(table)

        if auto_accept:
            action = "a"
        else:
            console.print("  [a]ccept / [r]eject / [s]kip / accept [A]ll / reject all [R] / [q]uit")
            action = input("  > ").strip().lower() or "s"

        if action == "q":
            break
        elif action == "a" or action == "A" or auto_accept:
            if action == "A":
                auto_accept = True
            name = d["full_name"]
            if name in classifications:
                classifications[name]["primary"] = d["suggested_primary"]
            accepted += 1
            _save_classifications(classifications)
            console.print(f"  [green]Accepted[/] → {d['suggested_primary']}")
        elif action == "R":
            console.print("  [yellow]Rejected all remaining[/]")
            break
        else:
            console.print("  [dim]Skipped[/]")

    console.print(f"\n[bold]Accepted {accepted} change(s)[/]")
    return accepted


def _save_classifications(classifications: dict[str, dict]):
    DATA_DIR.mkdir(exist_ok=True)
    CLASSIFICATIONS_FILE.write_text(json.dumps(classifications, indent=2))
