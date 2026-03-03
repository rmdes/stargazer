from stargazer.github_lists import GitHubListsManager

TAXONOMY = {
    "categories": [
        {
            "name": "AI & ML",
            "slug": "ai-ml",
            "subcategories": [
                {"name": "LLM Frameworks", "slug": "llm-frameworks"},
                {"name": "Computer Vision", "slug": "computer-vision"},
            ],
        },
        {
            "name": "DevOps",
            "slug": "devops",
            "subcategories": [
                {"name": "Kubernetes", "slug": "kubernetes"},
                {"name": "Docker", "slug": "docker-containers"},
            ],
        },
        {
            "name": "Web",
            "slug": "web",
            "subcategories": [],
        },
    ]
}


def test_pick_top_32_categories():
    classifications = {
        f"user/repo{i}": {"primary": f"cat-{i % 40}", "secondary": []}
        for i in range(200)
    }
    top = GitHubListsManager.pick_top_categories(classifications, limit=32)
    assert len(top) == 32
    # Each cat gets 5 repos (200/40), so all are equal -- just check count
    assert all(isinstance(slug, str) for slug in top)


def test_pick_top_categories_collapses_subcategories():
    classifications = {
        "r1": {"primary": "llm-frameworks", "secondary": []},
        "r2": {"primary": "llm-frameworks", "secondary": []},
        "r3": {"primary": "computer-vision", "secondary": []},
        "r4": {"primary": "ai-ml", "secondary": []},
        "r5": {"primary": "kubernetes", "secondary": []},
        "r6": {"primary": "web", "secondary": []},
    }
    top = GitHubListsManager.pick_top_categories(
        classifications, taxonomy=TAXONOMY, limit=2,
    )
    # ai-ml should be top (4 repos: 2 llm + 1 cv + 1 ai-ml), then devops (1)
    assert top[0] == "ai-ml"
    assert len(top) == 2


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


def test_build_assignments_rolls_up_subcategories():
    classifications = {
        "user/llm-tool": {"primary": "llm-frameworks", "secondary": []},
        "user/cv-tool": {"primary": "computer-vision", "secondary": []},
        "user/ai-tool": {"primary": "ai-ml", "secondary": []},
        "user/k8s-tool": {"primary": "kubernetes", "secondary": []},
    }
    stars = [
        {"full_name": "user/llm-tool", "node_id": "R_1"},
        {"full_name": "user/cv-tool", "node_id": "R_2"},
        {"full_name": "user/ai-tool", "node_id": "R_3"},
        {"full_name": "user/k8s-tool", "node_id": "R_4"},
    ]
    # Only parent-level lists exist
    list_ids = {"ai-ml": "UL_ai", "devops": "UL_devops"}
    assignments = GitHubListsManager.build_assignments(
        classifications, stars, list_ids, taxonomy=TAXONOMY,
    )
    assert assignments["R_1"] == ["UL_ai"]       # llm-frameworks → ai-ml
    assert assignments["R_2"] == ["UL_ai"]       # computer-vision → ai-ml
    assert assignments["R_3"] == ["UL_ai"]       # ai-ml → ai-ml (direct)
    assert assignments["R_4"] == ["UL_devops"]   # kubernetes → devops


def test_build_assignments_misc_fallback():
    classifications = {
        "user/repo1": {"primary": "ai-ml", "secondary": []},
        "user/repo2": {"primary": "obscure-category", "secondary": []},
    }
    stars = [
        {"full_name": "user/repo1", "node_id": "R_1"},
        {"full_name": "user/repo2", "node_id": "R_2"},
    ]
    list_ids = {"ai-ml": "UL_ai"}
    misc_list_id = "UL_misc"
    assignments = GitHubListsManager.build_assignments(
        classifications, stars, list_ids,
        taxonomy=TAXONOMY, misc_list_id=misc_list_id,
    )
    assert assignments["R_1"] == ["UL_ai"]
    assert assignments["R_2"] == [misc_list_id]  # falls back to misc


def test_build_assignments_no_repo_left_behind():
    """Every repo with a node_id must appear in assignments."""
    classifications = {
        "user/repo1": {"primary": "ai-ml", "secondary": []},
        "user/repo2": {"primary": "unknown-slug", "secondary": []},
        "user/repo3": {"primary": "web", "secondary": []},
    }
    stars = [
        {"full_name": "user/repo1", "node_id": "R_1"},
        {"full_name": "user/repo2", "node_id": "R_2"},
        {"full_name": "user/repo3", "node_id": "R_3"},
    ]
    list_ids = {"ai-ml": "UL_ai", "web": "UL_web"}
    misc_list_id = "UL_misc"
    assignments = GitHubListsManager.build_assignments(
        classifications, stars, list_ids,
        taxonomy=TAXONOMY, misc_list_id=misc_list_id,
    )
    assert len(assignments) == 3
    assert all(len(ids) > 0 for ids in assignments.values())
