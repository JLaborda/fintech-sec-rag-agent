"""Immutable raw lake writer."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def raw_object_prefix(cik: str, accession_number: str) -> str:
    return f"raw/edgar/{cik}/{accession_number}"


def write_raw_filing(
    *,
    s3_client: Any,
    bucket: str,
    ticker: str,
    cik: str,
    accession_number: str,
    form: str,
    filing_date: str,
    primary_document: str,
    raw_bytes: bytes,
    source_urls: list[str],
) -> str:
    prefix = raw_object_prefix(cik, accession_number)
    doc_key = f"{prefix}/{primary_document}"
    meta_key = f"{prefix}/provenance.json"

    # Never overwrite raw bytes: if object exists, refuse unless identical.
    existing = None
    try:
        existing = s3_client.get_object(Bucket=bucket, Key=doc_key)["Body"].read()
    except Exception:  # noqa: BLE001 — missing object is fine
        existing = None
    if existing is not None and existing != raw_bytes:
        raise FileExistsError(f"raw object already exists with different bytes: s3://{bucket}/{doc_key}")

    # Sidecar-first: SFN ignores provenance.json and runs on the primary document
    # event, so provenance must exist before the primary Object Created fires.
    sidecar = {
        "ticker": ticker,
        "cik": cik,
        "accession_number": accession_number,
        "form": form,
        "filing_date": filing_date,
        "source_urls": source_urls,
        "primary_document": primary_document,
        "ingested_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    s3_client.put_object(
        Bucket=bucket,
        Key=meta_key,
        Body=json.dumps(sidecar, indent=2).encode("utf-8"),
    )
    if existing is None:
        s3_client.put_object(Bucket=bucket, Key=doc_key, Body=raw_bytes)
    return f"s3://{bucket}/{doc_key}"


def load_provenance(s3_client: Any, bucket: str, cik: str, accession_number: str) -> dict[str, Any]:
    key = f"{raw_object_prefix(cik, accession_number)}/provenance.json"
    body = s3_client.get_object(Bucket=bucket, Key=key)["Body"].read()
    return json.loads(body)


def load_primary_text(
    s3_client: Any, bucket: str, cik: str, accession_number: str, primary_document: str
) -> str:
    key = f"{raw_object_prefix(cik, accession_number)}/{primary_document}"
    return s3_client.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8", errors="replace")
