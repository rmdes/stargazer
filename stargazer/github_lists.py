from collections import Counter

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

    def _graphql(self, query: str, variables: dict | None = None) -> dict:
        self.limiter.wait()
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        resp = httpx.post(
            "https://api.github.com/graphql",
            json=payload,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            raise RuntimeError(f"GraphQL error: {data['errors']}")
        return data

    def get_existing_lists(self) -> list[dict]:
        data = self._graphql(GET_LISTS)
        return data["data"]["viewer"]["lists"]["nodes"]

    def delete_all_lists(self):
        lists = self.get_existing_lists()
        if not lists:
            return
        console.print(f"Deleting {len(lists)} existing lists...")
        for lst in lists:
            self._graphql(DELETE_LIST, {"listId": lst["id"]})
            console.print(f"  Deleted: {lst['name']}")

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
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
        ) as progress:
            task = progress.add_task("Assigning repos to lists...", total=total)
            for node_id, list_ids in assignments.items():
                if list_ids:
                    self._graphql(UPDATE_ITEM_LISTS, {"itemId": node_id, "listIds": list_ids})
                progress.advance(task)

    @staticmethod
    def pick_top_categories(classifications: dict[str, dict], limit: int = 32) -> list[str]:
        counter = Counter()
        for cls in classifications.values():
            counter[cls["primary"]] += 1
        return [slug for slug, _ in counter.most_common(limit)]

    @staticmethod
    def build_assignments(
        classifications: dict[str, dict],
        stars: list[dict],
        list_ids: dict[str, str],
    ) -> dict[str, list[str]]:
        name_to_node = {s["full_name"]: s["node_id"] for s in stars}
        assignments = {}
        for full_name, cls in classifications.items():
            node_id = name_to_node.get(full_name)
            if not node_id:
                continue
            primary_list = list_ids.get(cls["primary"])
            if primary_list:
                assignments[node_id] = [primary_list]
        return assignments
