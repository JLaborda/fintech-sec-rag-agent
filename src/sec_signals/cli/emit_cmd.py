"""CLI emit (secondary re-emit / backfill) and validate."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from sec_signals.validate.emission_validator import validate_and_drop_uncited


def register(app: typer.Typer) -> None:
    @app.command("emit")
    def emit(
        tickers: str = typer.Option(..., "--tickers", help="Comma-separated demo tickers"),
        out: Path | None = typer.Option(None, "--out", help="Optional debug JSON output dir"),
        include_key_events: bool = typer.Option(True, "--include-key-events/--no-include-key-events"),
        accession: str | None = typer.Option(None, "--accession"),
        persist_warehouse: bool = typer.Option(
            True,
            "--persist-warehouse/--no-persist-warehouse",
            help="Write curated Parquet (default true)",
        ),
    ) -> None:
        """Re-emit / backfill hermetic signals (secondary path; not primary on-ingest)."""
        _ = (tickers, out, include_key_events, accession, persist_warehouse)
        typer.echo(
            "sec-signals emit is secondary re-emit/backfill only. "
            "Wire AWS clients/env to execute against live index+warehouse."
        )
        raise typer.Exit(code=4)

    @app.command("validate")
    def validate(file: Path = typer.Option(..., "--file")) -> None:
        """Validate a JSON emission against schema 0.1.0 + provenance rules."""
        payload = json.loads(file.read_text(encoding="utf-8"))
        emission = validate_and_drop_uncited(payload)
        typer.echo(f"valid emission for {emission.ticker.value} accession={emission.accession_number}")
