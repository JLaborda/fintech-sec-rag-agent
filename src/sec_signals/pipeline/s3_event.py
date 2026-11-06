"""S3 object-created event parsing for raw filings."""

from __future__ import annotations

import urllib.parse
from typing import Any


def parse_raw_s3_event(event: dict[str, Any]) -> dict[str, str]:
    records = event.get("Records") or []
    if not records:
        raise ValueError("S3 event missing Records")
    record = records[0]
    bucket = record["s3"]["bucket"]["name"]
    key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
    # raw/edgar/{cik}/{accession}/...
    parts = key.split("/")
    if len(parts) < 4 or parts[0] != "raw" or parts[1] != "edgar":
        raise ValueError(f"unexpected raw key: {key}")
    if key.endswith("provenance.json"):
        raise ValueError("ignore provenance sidecar events")
    return {
        "bucket": bucket,
        "key": key,
        "cik": parts[2],
        "accession_number": parts[3],
        "filename": parts[-1],
    }
