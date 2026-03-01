import json
from stargazer.taxonomy import TaxonomyManager


SAMPLE_TAXONOMY = {
    "categories": [
        {
            "name": "AI & Machine Learning",
            "slug": "ai-ml",
            "subcategories": [
                {"name": "LLM Tools", "slug": "llm-tools"},
                {"name": "ML Frameworks", "slug": "ml-frameworks"},
            ],
        },
        {
            "name": "Fediverse",
            "slug": "fediverse",
            "subcategories": [
                {"name": "ActivityPub", "slug": "activitypub"},
            ],
        },
    ]
}


def test_taxonomy_all_slugs():
    mgr = TaxonomyManager(SAMPLE_TAXONOMY)
    slugs = mgr.all_slugs()
    assert "ai-ml" in slugs
    assert "llm-tools" in slugs
    assert "fediverse" in slugs
    assert "activitypub" in slugs


def test_taxonomy_top_level_names():
    mgr = TaxonomyManager(SAMPLE_TAXONOMY)
    names = mgr.top_level_names()
    assert names == ["AI & Machine Learning", "Fediverse"]


def test_taxonomy_flat_list():
    mgr = TaxonomyManager(SAMPLE_TAXONOMY)
    flat = mgr.flat_list()
    assert len(flat) == 5
    assert any(c["slug"] == "llm-tools" and c["parent"] == "ai-ml" for c in flat)
