"""CLI emit (secondary re-emit / backfill) and validate."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from sec_signals.aws.runtime import build_runtime
from sec_signals.pipeline.cli_emit import run_cli_emit
from sec_signals.validate.emission_validator import validate_and_drop_uncited


def register(app: typer.Typer) -> None:
    @app.command("emit")
    def emit(
        tickers: str = typer.Option(..., "--tickers", help="Comma-separated demo tickers"),
        out: Path | None = typer.Option(None, "--out", help="Optional debug JSON output dir"),
        include_key_events: bool = typer.Option(
            True, "--include-key-events/--no-include-key-events"
        ),
        accession: str | None = typer.Option(None, "--accession"),
        persist_warehouse: bool = typer.Option(
            True,
            "--persist-warehouse/--no-persist-warehouse",
            help="Write curated Parquet (default true)",
        ),
    ) -> None:
        """Re-emit / backfill hermetic signals (secondary path; not primary on-ingest)."""
        try:
            runtime = build_runtime()
        except ValueError as exc:
            typer.echo(
                f"{exc}. sec-signals emit is secondary re-emit/backfill only; "
                "set SEC_SIGNALS_RAW_BUCKET and SEC_SIGNALS_AOSS_ENDPOINT."
            )
            raise typer.Exit(code=4) from exc

        ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
        results = run_cli_emit(
            tickers=ticker_list,
            runtime=runtime,
            persist_warehouse=persist_warehouse,
            accession=accession,
            write_debug=bool(out),
            include_key_events=include_key_events,
        )
        if out:
            out.mkdir(parents=True, exist_ok=True)
        exit_error = False
        for item in results:
            ticker_label = (
                item.ticker.value if hasattr(item.ticker, "value") else str(item.ticker)
            )
            if item.status == "emitted" and item.emission is not None:
                typer.echo(
                    f"emitted {ticker_label} accession={item.emission.accession_number}"
                    + (f" warehouse={item.warehouse_uri}" if item.warehouse_uri else "")
                )
                if out:
                    path = out / f"{ticker_label}.json"
                    path.write_text(
                        json.dumps(item.emission.model_dump(mode="json"), indent=2),
                        encoding="utf-8",
                    )
            else:
                exit_error = True
                typer.echo(
                    f"error {ticker_label}: {item.error_message or item.error_code}",
                    err=True,
                )
        if exit_error:
            raise typer.Exit(code=1)

    @app.command("validate")
    def validate(file: Path = typer.Option(..., "--file")) -> None:
        """Validate a JSON emission against schema 0.1.0 + provenance rules."""
        payload = json.loads(file.read_text(encoding="utf-8"))
        emission = validate_and_drop_uncited(payload)
        typer.echo(
            f"valid emission for {emission.ticker.value} "
            f"accession={emission.accession_number}"
        )
