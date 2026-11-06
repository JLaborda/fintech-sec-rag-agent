"""Curated Parquet warehouse writer."""

from __future__ import annotations

from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from sec_signals.models.warehouse import SignalFactorRow

FACTOR_SCHEMA_VERSION = "0.1.0"


def build_curated_key(
    *,
    ticker: str,
    filing_date: str,
    accession_number: str,
    pipeline_version: str,
    factor_schema_version: str = FACTOR_SCHEMA_VERSION,
) -> str:
    accession_safe = accession_number.replace("/", "-")
    pipeline_safe = pipeline_version.replace("/", "-")
    return (
        f"curated/signals/factor_schema_version={factor_schema_version}/"
        f"ticker={ticker}/filing_date={filing_date}/"
        f"part-{accession_safe}-{pipeline_safe}.parquet"
    )


def rows_to_table(rows: list[SignalFactorRow]) -> pa.Table:
    payloads = [row.model_dump(mode="json") for row in rows]
    return pa.Table.from_pylist(payloads)


def write_rows_local(path: str, rows: list[SignalFactorRow]) -> None:
    table = rows_to_table(rows)
    pq.write_table(table, path)


def write_rows_s3(
    *,
    s3_client: Any,
    bucket: str,
    key: str,
    rows: list[SignalFactorRow],
) -> str:
    import io

    table = rows_to_table(rows)
    buf = io.BytesIO()
    pq.write_table(table, buf)
    s3_client.put_object(Bucket=bucket, Key=key, Body=buf.getvalue())
    return f"s3://{bucket}/{key}"
