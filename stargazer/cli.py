import json
import os
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()

app = typer.Typer(help="Auto-sorting CLI for GitHub starred repos")
console = Console()


@app.command()
def fetch(
    delay: float = typer.Option(1.0, help="Seconds between API requests"),
    full: bool = typer.Option(False, help="Ignore cache, fetch all stars"),
):
    """Fetch all starred repos from GitHub."""
    from stargazer.fetcher import StarFetcher

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        console.print("[red]Error:[/] Set GITHUB_TOKEN or GH_TOKEN environment variable")
        raise typer.Exit(1)

    fetcher = StarFetcher(token=token, delay=delay)
    stars = fetcher.fetch_all(incremental=not full)
    console.print(f"[green]Done![/] {len(stars)} stars cached to data/stars.json")


@app.command()
def classify(
    batch_size: int = typer.Option(20, help="Repos per Claude API call"),
    delay: float = typer.Option(2.0, help="Seconds between Claude API calls"),
    full: bool = typer.Option(False, help="Ignore cache, reclassify all repos"),
):
    """Classify repos into taxonomy using Claude API."""
    from stargazer.fetcher import STARS_FILE
    from stargazer.taxonomy import TaxonomyManager, TAXONOMY_FILE
    from stargazer.classifier import Classifier

    if not STARS_FILE.exists():
        console.print("[red]Error:[/] No stars cached. Run 'stargazer fetch' first.")
        raise typer.Exit(1)

    stars = json.loads(STARS_FILE.read_text())

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[red]Error:[/] Set ANTHROPIC_API_KEY environment variable")
        raise typer.Exit(1)

    # Step 1: Generate or load taxonomy
    taxonomy_mgr = TaxonomyManager.load()
    if taxonomy_mgr is None:
        console.print("[bold]Generating taxonomy from your stars...[/]")
        import anthropic as anth

        client = anth.Anthropic(api_key=api_key)
        prompt = TaxonomyManager.build_prompt(stars)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        taxonomy_data = json.loads(raw)
        taxonomy_mgr = TaxonomyManager(taxonomy_data)
        taxonomy_mgr.display_tree()

        if not typer.confirm("\nApprove this taxonomy?"):
            console.print("Taxonomy saved to data/taxonomy.json -- edit it and re-run classify.")
            taxonomy_mgr.save()
            raise typer.Exit(0)
        taxonomy_mgr.save()
    else:
        console.print(f"[green]Using existing taxonomy[/] ({len(taxonomy_mgr.top_level_names())} categories)")

    # Step 2: Classify all repos
    classifier = Classifier(
        api_key=api_key,
        taxonomy=taxonomy_mgr.data,
        batch_size=batch_size,
        delay=delay,
    )
    classifications = classifier.classify_all(stars, full=full)
    console.print(f"[green]Done![/] {len(classifications)} repos classified")


@app.command()
def publish(
    delay: float = typer.Option(1.0, help="Seconds between GitHub API mutations"),
    skip_lists: bool = typer.Option(False, help="Skip GitHub Lists, only generate README"),
    resume: bool = typer.Option(False, help="Resume assignment using existing lists"),
    readme_path: str = typer.Option("README.md", help="Output path for generated README"),
):
    """Publish taxonomy to GitHub Lists and README."""
    from stargazer.fetcher import STARS_FILE
    from stargazer.taxonomy import TaxonomyManager
    from stargazer.classifier import CLASSIFICATIONS_FILE
    from stargazer.github_lists import GitHubListsManager
    from stargazer.renderer import render_readme

    if not STARS_FILE.exists() or not CLASSIFICATIONS_FILE.exists():
        console.print("[red]Error:[/] Run 'stargazer fetch' and 'stargazer classify' first.")
        raise typer.Exit(1)

    taxonomy_mgr = TaxonomyManager.load()
    if taxonomy_mgr is None:
        console.print("[red]Error:[/] No taxonomy found. Run 'stargazer classify' first.")
        raise typer.Exit(1)

    stars = json.loads(STARS_FILE.read_text())
    classifications = json.loads(CLASSIFICATIONS_FILE.read_text())

    # GitHub Lists
    if not skip_lists:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            console.print("[red]Error:[/] Set GITHUB_TOKEN or GH_TOKEN environment variable")
            raise typer.Exit(1)

        mgr = GitHubListsManager(token=token, delay=delay)
        top_slugs = GitHubListsManager.pick_top_categories(classifications, limit=32)

        if resume:
            existing = mgr.get_existing_lists()
            name_to_id = {lst["name"]: lst["id"] for lst in existing}
            cats = {c["slug"]: c for c in taxonomy_mgr.data["categories"]}
            list_ids = {}
            for slug in top_slugs:
                cat_name = cats.get(slug, {}).get("name", slug)
                if cat_name in name_to_id:
                    list_ids[slug] = name_to_id[cat_name]
            console.print(f"[green]Resuming:[/] Found {len(list_ids)}/{len(top_slugs)} existing lists")
        else:
            console.print(f"\n[bold]Top 32 categories for GitHub Lists:[/]")
            for i, slug in enumerate(top_slugs, 1):
                console.print(f"  {i:2d}. {slug}")

            if not typer.confirm("\nProceed? This will DELETE all existing lists and create new ones."):
                raise typer.Exit(0)

            mgr.delete_all_lists()
            list_ids = mgr.create_lists(taxonomy_mgr.data, top_slugs)

        assignments = GitHubListsManager.build_assignments(classifications, stars, list_ids)
        mgr.assign_repos(assignments)
        console.print(f"[green]Lists updated![/] {len(assignments)} repos assigned to {len(list_ids)} lists")

    # README
    readme = render_readme(taxonomy_mgr.data, stars, classifications)
    Path(readme_path).write_text(readme)
    console.print(f"[green]README generated![/] {readme_path}")


if __name__ == "__main__":
    app()
