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
def classify():
    """Classify repos into taxonomy using Claude API."""
    typer.echo("classify: not yet implemented")


@app.command()
def publish():
    """Publish taxonomy to GitHub Lists and README."""
    typer.echo("publish: not yet implemented")


if __name__ == "__main__":
    app()
