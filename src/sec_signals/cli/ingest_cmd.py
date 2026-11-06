"""CLI ingest helper — lands raw objects that trigger primary path."""

from __future__ import annotations

import typer


def register(app: typer.Typer) -> None:
    @app.command("ingest")
    def ingest(
        tickers: str = typer.Option(..., "--tickers"),
        region: str = typer.Option("eu-west-1", "--region"),
    ) -> None:
        """Fetch latest 10-K/10-K/A into immutable S3 lake (starts primary pipeline)."""
        _ = (tickers, region)
        typer.echo(
            "sec-signals ingest requires SEC_EDGAR_USER_AGENT and lake bucket env; "
            "raw object create triggers primary S3→Fargate index+emit."
        )
        raise typer.Exit(code=4)
