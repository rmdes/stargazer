import typer

app = typer.Typer(help="Auto-sorting CLI for GitHub starred repos")


@app.command()
def fetch():
    """Fetch all starred repos from GitHub."""
    typer.echo("fetch: not yet implemented")


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
