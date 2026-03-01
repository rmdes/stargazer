import json
import time
from pathlib import Path

import httpx
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from stargazer.rate_limiter import RateLimiter

STARS_QUERY = """
query($cursor: String) {
  viewer {
    starredRepositories(first: 100, after: $cursor, orderBy: {field: STARRED_AT, direction: DESC}) {
      edges {
        starredAt
        node {
          id
          nameWithOwner
          description
          primaryLanguage { name }
          repositoryTopics(first: 10) { nodes { topic { name } } }
          url
        }
      }
      pageInfo { hasNextPage endCursor }
      totalCount
    }
  }
}
"""

DATA_DIR = Path("data")
STARS_FILE = DATA_DIR / "stars.json"


class StarFetcher:
    def __init__(self, token: str, delay: float = 1.0):
        self.token = token
        self.limiter = RateLimiter(min_delay=delay)

    @staticmethod
    def _parse_edge(edge: dict) -> dict:
        node = edge["node"]
        lang = node.get("primaryLanguage")
        topics_raw = node.get("repositoryTopics", {}).get("nodes", [])
        return {
            "full_name": node["nameWithOwner"],
            "node_id": node["id"],
            "description": node.get("description") or "",
            "language": lang["name"] if lang else "",
            "topics": [t["topic"]["name"] for t in topics_raw],
            "url": node["url"],
            "starred_at": edge["starredAt"],
        }

    def fetch_all(self, incremental: bool = True) -> list[dict]:
        existing = self._load_existing() if incremental else []
        newest = existing[0]["starred_at"] if existing else None

        stars: list[dict] = []
        cursor = None
        stop = False

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
        ) as progress:
            task = progress.add_task("Fetching stars...", total=None)

            while not stop:
                self.limiter.wait()
                data = self._query(cursor)
                repo_data = data["data"]["viewer"]["starredRepositories"]

                if progress.tasks[task].total is None:
                    progress.update(task, total=repo_data["totalCount"])

                for edge in repo_data["edges"]:
                    star = self._parse_edge(edge)
                    if newest and star["starred_at"] <= newest:
                        stop = True
                        break
                    stars.append(star)
                    progress.advance(task)

                page_info = repo_data["pageInfo"]
                if not page_info["hasNextPage"]:
                    break
                cursor = page_info["endCursor"]

        all_stars = stars + existing
        self._save(all_stars)
        return all_stars

    def _query(self, cursor: str | None = None) -> dict:
        variables = {"cursor": cursor} if cursor else {}
        resp = httpx.post(
            "https://api.github.com/graphql",
            json={"query": STARS_QUERY, "variables": variables},
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()

    def _load_existing(self) -> list[dict]:
        if STARS_FILE.exists():
            return json.loads(STARS_FILE.read_text())
        return []

    def _save(self, stars: list[dict]):
        DATA_DIR.mkdir(exist_ok=True)
        STARS_FILE.write_text(json.dumps(stars, indent=2))
