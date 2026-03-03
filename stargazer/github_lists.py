from collections import Counter

import time

import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from stargazer.rate_limiter import RateLimiter

console = Console()

DELETE_LIST = """
mutation($listId: ID!) {
  deleteUserList(input: {listId: $listId}) { clientMutationId }
}"""

CREATE_LIST = """
mutation($name: String!, $description: String) {
  createUserList(input: {name: $name, description: $description, isPrivate: false}) {
    list { id name slug }
  }
}"""

UPDATE_ITEM_LISTS = """
mutation($itemId: ID!, $listIds: [ID!]!) {
  updateUserListsForItem(input: {itemId: $itemId, listIds: $listIds}) {
    clientMutationId
  }
}"""

GET_LISTS = """
{ viewer { lists(first: 50) { nodes { id name slug items(first: 1) { totalCount } } } } }
"""


class GitHubListsManager:
    def __init__(self, token: str, delay: float = 1.0):
        self.token = token
        self.limiter = RateLimiter(min_delay=delay)

    RETRYABLE_ERRORS = {"RESOURCE_LIMITS_EXCEEDED", "SERVICE_UNAVAILABLE", "LOADING"}

    def _graphql(self, query: str, variables: dict | None = None, retries: int = 5) -> dict:
        self.limiter.wait()
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        for attempt in range(retries):
            resp = httpx.post(
                "https://api.github.com/graphql",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
            if resp.status_code >= 500 and attempt < retries - 1:
                wait = 2 ** attempt * 3
                console.print(f"  [yellow]GitHub {resp.status_code}, retrying in {wait}s...[/]")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            if "errors" in data:
                errors = [e for e in data["errors"] if isinstance(e, dict)]
                error_types = {e.get("type", "") for e in errors}
                messages = " ".join(e.get("message", "") for e in errors)
                is_retryable = (
                    bool(error_types & self.RETRYABLE_ERRORS)
                    or "something went wrong" in messages.lower()
                )
                if is_retryable and attempt < retries - 1:
                    wait = 2 ** attempt * 5
                    label = (error_types - {""}).pop() if error_types - {""} else "Server error"
                    console.print(f"  [yellow]{label}, retrying in {wait}s...[/]")
                    time.sleep(wait)
                    continue
                raise RuntimeError(f"GraphQL error: {data['errors']}")
            return data
        raise RuntimeError("Max retries exceeded")

    def get_existing_lists(self) -> list[dict]:
        data = self._graphql(GET_LISTS)
        return data["data"]["viewer"]["lists"]["nodes"]

    def delete_all_lists(self):
        lists = self.get_existing_lists()
        if not lists:
            return
        console.print(f"Deleting {len(lists)} existing lists...")
        for lst in lists:
            try:
                self._graphql(DELETE_LIST, {"listId": lst["id"]})
                console.print(f"  Deleted: {lst['name']}")
            except RuntimeError as e:
                if "NOT_FOUND" in str(e):
                    console.print(f"  [dim]Already deleted: {lst['name']}[/]")
                else:
                    raise

    def create_lists(self, taxonomy: dict, top_slugs: list[str]) -> dict[str, str]:
        slug_to_id = {}
        cats = {c["slug"]: c for c in taxonomy["categories"]}

        console.print(f"Creating {len(top_slugs)} lists...")
        for slug in top_slugs:
            cat = cats.get(slug, {"name": slug, "description": ""})
            data = self._graphql(CREATE_LIST, {
                "name": cat["name"],
                "description": cat.get("description", ""),
            })
            list_data = data["data"]["createUserList"]["list"]
            slug_to_id[slug] = list_data["id"]
            console.print(f"  Created: {cat['name']}")

        return slug_to_id

    def assign_repos(self, assignments: dict[str, list[str]]):
        total = len(assignments)
        failed = 0
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
        ) as progress:
            task = progress.add_task("Assigning repos to lists...", total=total)
            for node_id, list_ids in assignments.items():
                if list_ids:
                    try:
                        self._graphql(UPDATE_ITEM_LISTS, {"itemId": node_id, "listIds": list_ids})
                    except RuntimeError:
                        failed += 1
                progress.advance(task)
        if failed:
            console.print(f"  [yellow]{failed} repos failed to assign (transient errors)[/]")

    @staticmethod
    def _child_to_parent(taxonomy: dict) -> dict[str, str]:
        """Build subcategory slug → parent slug mapping."""
        mapping = {}
        for cat in taxonomy.get("categories", []):
            for sub in cat.get("subcategories", []):
                mapping[sub["slug"]] = cat["slug"]
        return mapping

    @staticmethod
    def pick_top_categories(
        classifications: dict[str, dict],
        limit: int = 32,
        taxonomy: dict | None = None,
    ) -> list[str]:
        child_map = GitHubListsManager._child_to_parent(taxonomy) if taxonomy else {}
        counter = Counter()
        for cls in classifications.values():
            slug = cls["primary"]
            slug = child_map.get(slug, slug)
            counter[slug] += 1
        return [slug for slug, _ in counter.most_common(limit)]

    @staticmethod
    def build_assignments(
        classifications: dict[str, dict],
        stars: list[dict],
        list_ids: dict[str, str],
        taxonomy: dict | None = None,
        misc_list_id: str | None = None,
    ) -> dict[str, list[str]]:
        child_map = GitHubListsManager._child_to_parent(taxonomy) if taxonomy else {}
        name_to_node = {s["full_name"]: s["node_id"] for s in stars}
        assignments = {}
        for full_name, cls in classifications.items():
            node_id = name_to_node.get(full_name)
            if not node_id:
                continue
            slug = cls["primary"]
            # Try direct match, then parent rollup, then misc
            target = list_ids.get(slug) or list_ids.get(child_map.get(slug, ""))
            if not target and misc_list_id:
                target = misc_list_id
            if target:
                assignments[node_id] = [target]
        return assignments
