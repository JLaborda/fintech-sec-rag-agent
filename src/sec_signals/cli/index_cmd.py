"""CLI index / rebuild helper (ops)."""

from __future__ import annotations

import typer

from sec_signals.aws.runtime import build_runtime
from sec_signals.edgar.universe import cik_for_ticker
from sec_signals.models.enums import DemoTicker
from sec_signals.pipeline.cli_emit import resolve_latest_from_lake
from sec_signals.pipeline.index import index_accession
from sec_signals.pipeline.reindex import rebuild_accession


def register(app: typer.Typer) -> None:
    @app.command("index")
    def index(
        tickers: str = typer.Option(..., "--tickers"),
        rebuild: bool = typer.Option(False, "--rebuild"),
    ) -> None:
        """Parse/chunk/embed/index from lake into OpenSearch (ops rebuild helper)."""
        try:
            runtime = build_runtime()
        except ValueError as exc:
            typer.echo(
                f"{exc}. sec-signals index is an ops helper; "
                "primary path indexes during on-ingest Fargate."
            )
            raise typer.Exit(code=4) from exc

        ticker_list = [DemoTicker(t.strip().upper()) for t in tickers.split(",") if t.strip()]
        for ticker in ticker_list:
            filing = resolve_latest_from_lake(runtime, ticker)
            if rebuild:
                result = rebuild_accession(
                    s3_client=runtime.s3_client,
                    bucket=runtime.bucket,
                    cik=filing.cik,
                    accession_number=filing.accession_number,
                    indexer=runtime.indexer,
                )
            else:
                result = index_accession(
                    s3_client=runtime.s3_client,
                    bucket=runtime.bucket,
                    cik=cik_for_ticker(ticker),
                    accession_number=filing.accession_number,
                    indexer=runtime.indexer,
                )
            typer.echo(
                f"{'rebuilt' if rebuild else 'indexed'} {ticker.value} "
                f"accession={filing.accession_number} chunks={result['indexed_chunks']}"
            )
