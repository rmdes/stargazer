import json
import os
from pathlib import Path

import typer
from rich.console import Console

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
    classifications = classifier.classify_all(stars)
    console.print(f"[green]Done![/] {len(classifications)} repos classified")


@app.command()
def publish():
    """Publish taxonomy to GitHub Lists and README."""
    typer.echo("publish: not yet implemented")


if __name__ == "__main__":
    app()
