"""CLI ingest helper — lands raw objects that trigger primary path."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import boto3
import typer

from sec_signals.config import Settings, get_settings
from sec_signals.edgar.client import EdgarClient
from sec_signals.pipeline.ingest import ingest_tickers


def build_edgar_and_s3(settings: Settings) -> tuple[EdgarClient, Any, str]:
    if not settings.edgar_user_agent:
        raise ValueError("SEC_EDGAR_USER_AGENT is required")
    if not settings.raw_bucket:
        raise ValueError("SEC_SIGNALS_RAW_BUCKET is required")
    edgar = EdgarClient(user_agent=settings.edgar_user_agent)
    s3 = boto3.client("s3", region_name=settings.aws_region)
    return edgar, s3, settings.raw_bucket


def register(app: typer.Typer) -> None:
    @app.command("ingest")
    def ingest(
        tickers: str = typer.Option(..., "--tickers"),
        region: str = typer.Option("eu-west-1", "--region"),
    ) -> None:
        """Fetch latest 10-K/10-K/A into immutable S3 lake (starts primary pipeline)."""
        settings = replace(get_settings(), aws_region=region)
        try:
            edgar, s3, bucket = build_edgar_and_s3(settings)
        except ValueError as exc:
            typer.echo(str(exc))
            raise typer.Exit(code=4) from exc

        ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
        results = ingest_tickers(ticker_list, edgar=edgar, s3_client=s3, bucket=bucket)
        for item in results:
            typer.echo(
                f"ingested {item['ticker']} accession={item['accession_number']} uri={item['uri']}"
            )
        typer.echo(
            "raw object create should trigger primary S3→Step Functions→Fargate index+emit."
        )
