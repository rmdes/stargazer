import json
from pathlib import Path

import anthropic
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from stargazer.rate_limiter import RateLimiter
from stargazer.taxonomy import TaxonomyManager

DATA_DIR = Path("data")
CLASSIFICATIONS_FILE = DATA_DIR / "classifications.json"

CLASSIFY_PROMPT = """Classify these GitHub repositories into the taxonomy below. For each repo, assign:
- primary: the single best-fit category slug
- secondary: 0-2 additional category slugs (only if truly relevant)

Use ONLY slugs from this taxonomy:

{taxonomy}

Repositories to classify:

{repos}

Return ONLY valid JSON (no markdown, no explanation):
{{
  "classifications": [
    {{"full_name": "owner/repo", "primary": "slug", "secondary": ["slug2"]}}
  ]
}}"""


DEFAULT_CATEGORY = "uncategorized"


class Classifier:
    def __init__(self, api_key: str, taxonomy: dict, batch_size: int = 20, delay: float = 2.0):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.taxonomy = taxonomy
        self.batch_size = batch_size
        self.limiter = RateLimiter(min_delay=delay)
        self._valid_slugs = TaxonomyManager(taxonomy).all_slugs()

    def classify_all(self, stars: list[dict], full: bool = False) -> dict[str, dict]:
        existing = {} if full else self._load_existing()
        unclassified = [s for s in stars if s["full_name"] not in existing]

        if not unclassified:
            return existing

        batches = [unclassified[i:i + self.batch_size] for i in range(0, len(unclassified), self.batch_size)]

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
        ) as progress:
            task = progress.add_task("Classifying repos...", total=len(unclassified))

            for batch in batches:
                self.limiter.wait()
                prompt = self._build_batch_prompt(batch)
                response = self._call_claude(prompt)
                results = self._parse_response(response)

                for result in results:
                    primary = result["primary"]
                    if primary not in self._valid_slugs:
                        primary = DEFAULT_CATEGORY
                    secondary = [s for s in result.get("secondary", []) if s in self._valid_slugs]
                    existing[result["full_name"]] = {
                        "primary": primary,
                        "secondary": secondary,
                    }

                progress.advance(task, advance=len(batch))
                self._save(existing)

        return existing

    def _build_batch_prompt(self, repos: list[dict]) -> str:
        mgr = TaxonomyManager(self.taxonomy)
        slugs = sorted(mgr.all_slugs())
        taxonomy_str = ", ".join(slugs)
        repo_lines = "\n".join(TaxonomyManager.format_repo_for_prompt(r) for r in repos)
        return CLASSIFY_PROMPT.format(taxonomy=taxonomy_str, repos=repo_lines)

    def _call_claude(self, prompt: str) -> str:
        message = self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    @staticmethod
    def _parse_response(text: str) -> list[dict]:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        data = json.loads(text)
        return data["classifications"]

    def _load_existing(self) -> dict[str, dict]:
        if CLASSIFICATIONS_FILE.exists():
            return json.loads(CLASSIFICATIONS_FILE.read_text())
        return {}

    def _save(self, classifications: dict[str, dict]):
        DATA_DIR.mkdir(exist_ok=True)
        CLASSIFICATIONS_FILE.write_text(json.dumps(classifications, indent=2))


def ensure_default_category(taxonomy: dict) -> bool:
    """Add the default 'uncategorized' category if missing. Returns True if added."""
    slugs = {cat["slug"] for cat in taxonomy["categories"]}
    if DEFAULT_CATEGORY in slugs:
        return False
    taxonomy["categories"].append({
        "name": "Uncategorized",
        "slug": DEFAULT_CATEGORY,
        "description": "Repos that don't fit neatly into any other category.",
        "subcategories": [],
    })
    return True
