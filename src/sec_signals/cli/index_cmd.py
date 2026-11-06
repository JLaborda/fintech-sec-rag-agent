"""CLI index / rebuild helper (ops)."""

from __future__ import annotations

import typer


def register(app: typer.Typer) -> None:
    @app.command("index")
    def index(
        tickers: str = typer.Option(..., "--tickers"),
        rebuild: bool = typer.Option(False, "--rebuild"),
    ) -> None:
        """Parse/chunk/embed/index from lake into OpenSearch (ops rebuild helper)."""
        _ = (tickers, rebuild)
        typer.echo(
            "sec-signals index is an ops helper; primary path indexes during on-ingest Fargate."
        )
        raise typer.Exit(code=4)
