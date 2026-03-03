import json
from unittest.mock import MagicMock, patch
from stargazer.classifier import Classifier, DEFAULT_CATEGORY, ensure_default_category


TAXONOMY = {
    "categories": [
        {"name": "AI", "slug": "ai", "subcategories": [{"name": "LLM", "slug": "llm"}]},
        {"name": "Web", "slug": "web", "subcategories": []},
    ]
}

REPO = {
    "full_name": "user/llm-tool",
    "node_id": "R_123",
    "description": "An LLM tool",
    "language": "Python",
    "topics": ["ai", "llm"],
    "url": "https://github.com/user/llm-tool",
    "starred_at": "2026-01-01T00:00:00Z",
}


def test_build_classification_prompt():
    c = Classifier.__new__(Classifier)
    c.taxonomy = TAXONOMY
    prompt = c._build_batch_prompt([REPO])
    assert "user/llm-tool" in prompt
    assert "ai" in prompt.lower()


def test_parse_classification_response():
    raw = json.dumps({
        "classifications": [
            {"full_name": "user/llm-tool", "primary": "llm", "secondary": ["ai"]}
        ]
    })
    result = Classifier._parse_response(raw)
    assert result[0]["full_name"] == "user/llm-tool"
    assert result[0]["primary"] == "llm"
    assert result[0]["secondary"] == ["ai"]


def test_classify_all_replaces_invalid_primary_with_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()

    c = Classifier.__new__(Classifier)
    c.taxonomy = TAXONOMY
    c.batch_size = 20
    c._valid_slugs = {"ai", "llm", "web"}
    c.limiter = MagicMock()

    response = json.dumps({
        "classifications": [
            {"full_name": "user/llm-tool", "primary": "invented-slug", "secondary": ["ai", "fake"]}
        ]
    })
    c._call_claude = MagicMock(return_value=response)

    result = c.classify_all([REPO], full=True)
    assert result["user/llm-tool"]["primary"] == DEFAULT_CATEGORY
    assert result["user/llm-tool"]["secondary"] == ["ai"]


def test_ensure_default_category_adds_when_missing():
    taxonomy = {"categories": [{"name": "AI", "slug": "ai", "subcategories": []}]}
    added = ensure_default_category(taxonomy)
    assert added is True
    slugs = {c["slug"] for c in taxonomy["categories"]}
    assert DEFAULT_CATEGORY in slugs


def test_ensure_default_category_noop_when_present():
    taxonomy = {"categories": [
        {"name": "AI", "slug": "ai", "subcategories": []},
        {"name": "Uncategorized", "slug": DEFAULT_CATEGORY, "subcategories": []},
    ]}
    added = ensure_default_category(taxonomy)
    assert added is False
    assert len(taxonomy["categories"]) == 2
