import json
import random
from pathlib import Path

from rich.console import Console
from rich.tree import Tree

DATA_DIR = Path("data")
TAXONOMY_FILE = DATA_DIR / "taxonomy.json"

console = Console()

TAXONOMY_PROMPT = """Analyze these {count} GitHub repositories and propose an optimal category taxonomy for organizing a collection of {total}+ starred repos.

Requirements:
- Create 20-40 top-level categories (the best 32 will become GitHub Lists)
- Each top-level category can have 2-8 subcategories
- Categories should be thematic (e.g. "Fediverse", "DevOps"), NOT language-based
- Each category needs a short slug (lowercase, hyphens) and a human-readable name
- Optimize for discoverability: a developer should intuitively know where to find a repo

Return ONLY valid JSON in this exact format (no markdown, no explanation):
{{
  "categories": [
    {{
      "name": "Human Readable Name",
      "slug": "short-slug",
      "description": "One sentence describing this category",
      "subcategories": [
        {{"name": "Subcategory Name", "slug": "sub-slug"}}
      ]
    }}
  ]
}}

Here are the repositories to analyze:

{repos}"""


class TaxonomyManager:
    def __init__(self, data: dict):
        self.data = data

    @classmethod
    def load(cls) -> "TaxonomyManager | None":
        if TAXONOMY_FILE.exists():
            return cls(json.loads(TAXONOMY_FILE.read_text()))
        return None

    def save(self):
        DATA_DIR.mkdir(exist_ok=True)
        TAXONOMY_FILE.write_text(json.dumps(self.data, indent=2))

    def all_slugs(self) -> set[str]:
        slugs = set()
        for cat in self.data["categories"]:
            slugs.add(cat["slug"])
            for sub in cat.get("subcategories", []):
                slugs.add(sub["slug"])
        return slugs

    def top_level_names(self) -> list[str]:
        return [c["name"] for c in self.data["categories"]]

    def flat_list(self) -> list[dict]:
        result = []
        for cat in self.data["categories"]:
            result.append({"name": cat["name"], "slug": cat["slug"], "parent": None})
            for sub in cat.get("subcategories", []):
                result.append({"name": sub["name"], "slug": sub["slug"], "parent": cat["slug"]})
        return result

    def display_tree(self):
        tree = Tree("[bold]Taxonomy[/bold]")
        for cat in self.data["categories"]:
            desc = cat.get("description", "")
            branch = tree.add(f"[bold cyan]{cat['name']}[/] [dim]({cat['slug']})[/] {desc}")
            for sub in cat.get("subcategories", []):
                branch.add(f"{sub['name']} [dim]({sub['slug']})[/]")
        console.print(tree)

    @staticmethod
    def sample_repos(stars: list[dict], count: int = 200) -> list[dict]:
        if len(stars) <= count:
            return stars
        step = len(stars) // count
        return [stars[i * step] for i in range(count)]

    @staticmethod
    def format_repo_for_prompt(repo: dict) -> str:
        topics = ", ".join(repo.get("topics", [])[:5])
        desc = (repo.get("description") or "")[:100]
        return f"- {repo['full_name']} [{repo.get('language', '')}] {desc} ({topics})"

    @classmethod
    def build_prompt(cls, stars: list[dict]) -> str:
        sample = cls.sample_repos(stars)
        repo_lines = "\n".join(cls.format_repo_for_prompt(r) for r in sample)
        return TAXONOMY_PROMPT.format(count=len(sample), total=len(stars), repos=repo_lines)
