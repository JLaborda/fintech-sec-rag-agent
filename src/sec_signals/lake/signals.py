"""Optional debug JSON signal IO under signals/ prefix."""

from __future__ import annotations

import json
from typing import Any

from sec_signals.models.emission import SignalEmission


def debug_signal_key(
    *,
    ticker: str,
    accession_number: str,
    pipeline_version: str,
    factor_schema_version: str = "0.1.0",
) -> str:
    return (
        f"signals/{factor_schema_version}/{ticker}/"
        f"{accession_number}/{pipeline_version}.json"
    )


def write_debug_json(
    *,
    s3_client: Any,
    bucket: str,
    emission: SignalEmission,
) -> str:
    key = debug_signal_key(
        ticker=emission.ticker.value,
        accession_number=emission.accession_number,
        pipeline_version=emission.model_or_pipeline_version,
        factor_schema_version=emission.factor_schema_version,
    )
    body = emission.model_dump_json().encode("utf-8")
    s3_client.put_object(Bucket=bucket, Key=key, Body=body)
    return f"s3://{bucket}/{key}"


def dumps_emission(emission: SignalEmission) -> str:
    return json.dumps(emission.model_dump(mode="json"), indent=2)
