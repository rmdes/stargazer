from stargazer.renderer import render_readme


TAXONOMY = {
    "categories": [
        {
            "name": "AI",
            "slug": "ai",
            "description": "AI tools",
            "subcategories": [{"name": "LLM", "slug": "llm"}],
        },
    ]
}

STARS = [
    {"full_name": "user/ai-tool", "node_id": "R_1", "description": "An AI tool", "language": "Python", "topics": [], "url": "https://github.com/user/ai-tool", "starred_at": "2026-01-01"},
    {"full_name": "user/llm-lib", "node_id": "R_2", "description": "LLM library", "language": "Rust", "topics": [], "url": "https://github.com/user/llm-lib", "starred_at": "2026-01-02"},
]

CLASSIFICATIONS = {
    "user/ai-tool": {"primary": "ai", "secondary": ["llm"]},
    "user/llm-lib": {"primary": "llm", "secondary": []},
}


def test_render_readme_contains_sections():
    md = render_readme(TAXONOMY, STARS, CLASSIFICATIONS)
    assert "## AI" in md
    assert "### LLM" in md
    assert "[user/ai-tool]" in md
    assert "[user/llm-lib]" in md


def test_render_readme_multi_category():
    md = render_readme(TAXONOMY, STARS, CLASSIFICATIONS)
    # user/ai-tool has primary=ai, secondary=[llm], so it appears in both
    ai_section = md.split("## AI")[1].split("## ")[0] if "## AI" in md else ""
    assert "user/ai-tool" in ai_section


def test_render_readme_has_stats():
    md = render_readme(TAXONOMY, STARS, CLASSIFICATIONS)
    assert "2 starred repos" in md or "**2**" in md
