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


def test_build_audit_prompt_includes_current_classification():
    auditor = Auditor.__new__(Auditor)
    auditor.taxonomy = TAXONOMY
    classifications = {
        "user/llm-tool": {"primary": "web", "secondary": []},
    }
    prompt = auditor._build_audit_prompt([REPO], classifications)
    assert "user/llm-tool" in prompt
    assert "web" in prompt
    assert "correct" in prompt.lower()


def test_build_audit_prompt_multiple_repos():
    auditor = Auditor.__new__(Auditor)
    auditor.taxonomy = TAXONOMY
    classifications = {
        "user/llm-tool": {"primary": "ai", "secondary": ["llm"]},
        "org/web-framework": {"primary": "web", "secondary": []},
    }
    prompt = auditor._build_audit_prompt([REPO, REPO2], classifications)
    assert "user/llm-tool" in prompt
    assert "org/web-framework" in prompt


def test_parse_audit_response_returns_disagreements():
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
    result = Auditor._parse_audit_response(raw)
    assert len(result) == 1
    assert result[0]["full_name"] == "user/llm-tool"
    assert result[0]["suggested_primary"] == "llm"
    assert result[0]["reason"] == "LLM is a better fit than web"


def test_parse_audit_response_handles_markdown_fences():
    raw = '```json\n' + json.dumps({
        "audits": [
            {"full_name": "user/llm-tool", "correct": False,
             "suggested_primary": "ai", "reason": "Wrong category"},
        ]
    }) + '\n```'
    result = Auditor._parse_audit_response(raw)
    assert len(result) == 1
    assert result[0]["suggested_primary"] == "ai"


def test_parse_audit_all_correct_returns_empty():
    raw = json.dumps({
        "audits": [
            {"full_name": "user/llm-tool", "correct": True},
            {"full_name": "org/web-framework", "correct": True},
        ]
    })
    result = Auditor._parse_audit_response(raw)
    assert result == []
