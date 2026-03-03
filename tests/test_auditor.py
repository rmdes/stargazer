import json

from stargazer.auditor import Auditor


TAXONOMY = {
    "categories": [
        {"name": "AI", "slug": "ai", "subcategories": [{"name": "LLM", "slug": "llm"}]},
        {"name": "Web", "slug": "web", "subcategories": []},
        {"name": "DevOps", "slug": "devops", "subcategories": []},
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

REPO2 = {
    "full_name": "org/web-framework",
    "node_id": "R_456",
    "description": "A web framework",
    "language": "TypeScript",
    "topics": ["web", "framework"],
    "url": "https://github.com/org/web-framework",
    "starred_at": "2026-01-02T00:00:00Z",
}


def _make_auditor():
    auditor = Auditor.__new__(Auditor)
    auditor.taxonomy = TAXONOMY
    auditor._valid_slugs = {"ai", "llm", "web", "devops"}
    return auditor


def test_build_audit_prompt_includes_current_classification():
    auditor = _make_auditor()
    classifications = {
        "user/llm-tool": {"primary": "web", "secondary": []},
    }
    prompt = auditor._build_audit_prompt([REPO], classifications)
    assert "user/llm-tool" in prompt
    assert "web" in prompt
    assert "correct" in prompt.lower()


def test_build_audit_prompt_multiple_repos():
    auditor = _make_auditor()
    classifications = {
        "user/llm-tool": {"primary": "ai", "secondary": ["llm"]},
        "org/web-framework": {"primary": "web", "secondary": []},
    }
    prompt = auditor._build_audit_prompt([REPO, REPO2], classifications)
    assert "user/llm-tool" in prompt
    assert "org/web-framework" in prompt


def test_parse_audit_response_returns_disagreements():
    auditor = _make_auditor()
    raw = json.dumps({
        "audits": [
            {
                "full_name": "user/llm-tool",
                "correct": False,
                "suggested_primary": "llm",
                "reason": "LLM is a better fit than web",
            },
            {
                "full_name": "org/web-framework",
                "correct": True,
            },
        ]
    })
    result = auditor._parse_audit_response(raw)
    assert len(result) == 1
    assert result[0]["full_name"] == "user/llm-tool"
    assert result[0]["suggested_primary"] == "llm"
    assert result[0]["reason"] == "LLM is a better fit than web"


def test_parse_audit_response_handles_markdown_fences():
    auditor = _make_auditor()
    raw = '```json\n' + json.dumps({
        "audits": [
            {"full_name": "user/llm-tool", "correct": False,
             "suggested_primary": "ai", "reason": "Wrong category"},
        ]
    }) + '\n```'
    result = auditor._parse_audit_response(raw)
    assert len(result) == 1
    assert result[0]["suggested_primary"] == "ai"


def test_parse_audit_all_correct_returns_empty():
    auditor = _make_auditor()
    raw = json.dumps({
        "audits": [
            {"full_name": "user/llm-tool", "correct": True},
            {"full_name": "org/web-framework", "correct": True},
        ]
    })
    result = auditor._parse_audit_response(raw)
    assert result == []


def test_parse_audit_response_drops_invalid_suggested_slug():
    auditor = _make_auditor()
    raw = json.dumps({
        "audits": [
            {
                "full_name": "user/llm-tool",
                "correct": False,
                "suggested_primary": "invented-slug",
                "reason": "Some reason",
            },
            {
                "full_name": "org/web-framework",
                "correct": False,
                "suggested_primary": "devops",
                "reason": "Valid suggestion",
            },
        ]
    })
    result = auditor._parse_audit_response(raw)
    assert len(result) == 1
    assert result[0]["full_name"] == "org/web-framework"
    assert result[0]["suggested_primary"] == "devops"
