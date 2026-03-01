from stargazer.github_lists import GitHubListsManager


def test_pick_top_32_categories():
    classifications = {
        f"user/repo{i}": {"primary": f"cat-{i % 40}", "secondary": []}
        for i in range(200)
    }
    top = GitHubListsManager.pick_top_categories(classifications, limit=32)
    assert len(top) == 32
    # Each cat gets 5 repos (200/40), so all are equal -- just check count
    assert all(isinstance(slug, str) for slug in top)


def test_build_list_assignments():
    classifications = {
        "user/repo1": {"primary": "ai", "secondary": ["web"]},
        "user/repo2": {"primary": "ai", "secondary": []},
        "user/repo3": {"primary": "web", "secondary": []},
    }
    stars = [
        {"full_name": "user/repo1", "node_id": "R_1"},
        {"full_name": "user/repo2", "node_id": "R_2"},
        {"full_name": "user/repo3", "node_id": "R_3"},
    ]
    list_ids = {"ai": "UL_ai", "web": "UL_web"}
    assignments = GitHubListsManager.build_assignments(classifications, stars, list_ids)
    assert assignments["R_1"] == ["UL_ai"]  # primary only for GitHub Lists
    assert assignments["R_2"] == ["UL_ai"]
    assert assignments["R_3"] == ["UL_web"]
