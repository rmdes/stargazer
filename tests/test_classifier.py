import json
from unittest.mock import MagicMock, patch
from stargazer.classifier import Classifier


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
