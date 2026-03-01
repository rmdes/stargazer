import json
from unittest.mock import AsyncMock, patch
from stargazer.fetcher import StarFetcher


MOCK_RESPONSE = {
    "data": {
        "viewer": {
            "starredRepositories": {
                "edges": [
                    {
                        "starredAt": "2026-03-01T13:18:42Z",
                        "node": {
                            "id": "R_kgDORbcgzg",
                            "nameWithOwner": "user/repo",
                            "description": "A test repo",
                            "primaryLanguage": {"name": "Python"},
                            "repositoryTopics": {
                                "nodes": [{"topic": {"name": "cli"}}]
                            },
                            "url": "https://github.com/user/repo",
                        },
                    }
                ],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "totalCount": 1,
            }
        }
    }
}


def test_parse_star_edge():
    edge = MOCK_RESPONSE["data"]["viewer"]["starredRepositories"]["edges"][0]
    star = StarFetcher._parse_edge(edge)
    assert star["full_name"] == "user/repo"
    assert star["description"] == "A test repo"
    assert star["language"] == "Python"
    assert star["topics"] == ["cli"]
    assert star["url"] == "https://github.com/user/repo"
    assert star["starred_at"] == "2026-03-01T13:18:42Z"
    assert star["node_id"] == "R_kgDORbcgzg"
