from collections import defaultdict


def render_readme(taxonomy: dict, stars: list[dict], classifications: dict[str, dict]) -> str:
    star_map = {s["full_name"]: s for s in stars}

    # Build category -> repos mapping (multi-category)
    cat_repos: dict[str, list[str]] = defaultdict(list)
    for full_name, cls in classifications.items():
        cat_repos[cls["primary"]].append(full_name)
        for sec in cls.get("secondary", []):
            cat_repos[sec].append(full_name)

    lines = []
    lines.append("# Stargazer")
    lines.append("")
    lines.append(f"**{len(stars)}** starred repos organized into "
                 f"**{len(taxonomy['categories'])}** categories.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Table of contents
    lines.append("## Table of Contents")
    lines.append("")
    for cat in taxonomy["categories"]:
        count = len(cat_repos.get(cat["slug"], []))
        lines.append(f"- [{cat['name']}](#{cat['slug']}) ({count})")
        for sub in cat.get("subcategories", []):
            sub_count = len(cat_repos.get(sub["slug"], []))
            if sub_count > 0:
                lines.append(f"  - [{sub['name']}](#{sub['slug']}) ({sub_count})")
    lines.append("")

    # Category sections
    for cat in taxonomy["categories"]:
        lines.append(f"## {cat['name']}")
        if cat.get("description"):
            lines.append(f"_{cat['description']}_")
        lines.append("")

        # Top-level repos (primary = this category)
        top_repos = cat_repos.get(cat["slug"], [])
        if top_repos:
            for fn in sorted(top_repos):
                repo = star_map.get(fn)
                if repo:
                    lines.append(_format_repo(repo))
            lines.append("")

        # Subcategory sections
        for sub in cat.get("subcategories", []):
            sub_repos = cat_repos.get(sub["slug"], [])
            if sub_repos:
                lines.append(f"### {sub['name']}")
                lines.append("")
                for fn in sorted(sub_repos):
                    repo = star_map.get(fn)
                    if repo:
                        lines.append(_format_repo(repo))
                lines.append("")

    return "\n".join(lines)


def _format_repo(repo: dict) -> str:
    lang = f"`{repo['language']}`" if repo.get("language") else ""
    desc = repo.get("description", "")[:120]
    return f"- [{repo['full_name']}]({repo['url']}) {lang} -- {desc}"
