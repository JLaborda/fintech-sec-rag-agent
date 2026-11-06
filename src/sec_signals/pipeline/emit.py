"""Emit pipeline: retrieve → extract → validate → warehouse persist."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sec_signals.extract.factor_extractor import FactorExtractor
from sec_signals.lake.signals import write_debug_json
from sec_signals.models.emission import SignalEmission
from sec_signals.models.enums import DemoTicker, FormType
from sec_signals.models.warehouse import flatten_emission
from sec_signals.retrieve.retriever import FactorRetriever
from sec_signals.validate.emission_validator import validate_and_drop_uncited
from sec_signals.version import MODEL_OR_PIPELINE_VERSION
from sec_signals.warehouse.parquet_writer import build_curated_key, write_rows_s3

DISCLAIMER = "Research / decision-support only — not investment advice."


def emit_for_filing(
    *,
    retriever: FactorRetriever,
    extractor: FactorExtractor,
    ticker: DemoTicker | str,
    cik: str,
    accession_number: str,
    form: FormType | str,
    filing_date: str,
    s3_client: Any | None = None,
    bucket: str | None = None,
    persist_warehouse: bool = True,
    write_debug: bool = False,
    pipeline_version: str = MODEL_OR_PIPELINE_VERSION,
) -> tuple[SignalEmission, str | None]:
    chunks = retriever.retrieve_for_factors(
        ticker=ticker,
        accession_number=accession_number,
        filing_date=filing_date,
        form=form,
        cik=cik,
    )
    draft = extractor.extract(chunks)
    payload = {
        "factor_schema_version": "0.1.0",
        "model_or_pipeline_version": pipeline_version,
        "ticker": ticker.value if isinstance(ticker, DemoTicker) else ticker,
        "cik": cik,
        "accession_number": accession_number,
        "form": form.value if isinstance(form, FormType) else form,
        "filing_date": filing_date,
        "factors": draft.get("factors", []),
        "key_events": draft.get("key_events") or None,
        "disclaimer": DISCLAIMER,
        "emitted_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    if payload["key_events"] is None:
        payload.pop("key_events")
    emission = validate_and_drop_uncited(payload)

    warehouse_uri: str | None = None
    if persist_warehouse:
        if s3_client is None or not bucket:
            raise ValueError("s3_client and bucket required when persist_warehouse=True")
        rows = flatten_emission(emission)
        key = build_curated_key(
            ticker=emission.ticker.value,
            filing_date=emission.filing_date.isoformat(),
            accession_number=emission.accession_number,
            pipeline_version=emission.model_or_pipeline_version,
        )
        warehouse_uri = write_rows_s3(s3_client=s3_client, bucket=bucket, key=key, rows=rows)
        if write_debug:
            write_debug_json(s3_client=s3_client, bucket=bucket, emission=emission)
    return emission, warehouse_uri
