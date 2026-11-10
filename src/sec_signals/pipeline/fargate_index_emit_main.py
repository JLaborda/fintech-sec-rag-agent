"""Fargate entry: primary index + emit + warehouse (or index-only rebuild)."""

from __future__ import annotations

import argparse
import json
import time
from typing import Any, Protocol

from sec_signals.aws.runtime import build_runtime
from sec_signals.lake.raw import load_provenance
from sec_signals.pipeline.emit import emit_for_filing
from sec_signals.pipeline.index import index_accession
from sec_signals.pipeline.reindex import rebuild_accession


class _Indexer(Protocol):
    def upsert_chunks(self, chunks): ...  # noqa: ANN001


def claim_accession_for_index(*, bucket: str, cik: str, accession_number: str) -> bool:
    """Best-effort accession-level claim before index/emit (dedupe concurrent S3 events).

    TODO: implement atomic claim (e.g. S3 PutObject if-none-match / DynamoDB conditional
    write) when an idempotency store is available. Returns True so the current path proceeds.
    """
    _ = (bucket, cik, accession_number)
    return True


def wait_until_accession_searchable(
    *,
    search_client: Any,
    index_name: str,
    accession_number: str,
    attempts: int = 8,
    delay_seconds: float = 0.5,
) -> bool:
    """Poll AOSS until at least one chunk for the accession is visible (or attempts exhausted)."""
    body = {"size": 1, "query": {"term": {"accession_number": accession_number}}}
    for _ in range(max(1, attempts)):
        try:
            result = search_client.search(index=index_name, body=body)
            hits = result.get("hits", {}).get("hits", [])
            if hits:
                return True
        except Exception:  # noqa: BLE001 — visibility poll is best-effort
            pass
        time.sleep(delay_seconds)
    return False


def run_index_emit(
    *,
    s3_client: Any,
    bucket: str,
    cik: str,
    accession_number: str,
    indexer: _Indexer,
    retriever: Any | None = None,
    extractor: Any | None = None,
    mode: str = "index_emit",
    aoss_client: Any | None = None,
    wait_for_visibility: bool = True,
) -> dict[str, Any]:
    """Run index and/or emit for one accession according to ``mode``."""
    if not claim_accession_for_index(
        bucket=bucket, cik=cik, accession_number=accession_number
    ):
        return {
            "mode": mode,
            "skipped": True,
            "reason": "accession_claim_held",
            "indexed_chunks": 0,
            "warehouse_uri": None,
        }

    indexed: dict[str, Any]
    if mode == "rebuild":
        indexed = rebuild_accession(
            s3_client=s3_client,
            bucket=bucket,
            cik=cik,
            accession_number=accession_number,
            indexer=indexer,  # type: ignore[arg-type]
        )
    elif mode == "emit_only":
        provenance = load_provenance(s3_client, bucket, cik, accession_number)
        indexed = {
            "ticker": provenance["ticker"],
            "cik": cik,
            "accession_number": accession_number,
            "filing_date": provenance["filing_date"],
            "form": provenance["form"],
            "indexed_chunks": 0,
            "provenance": provenance,
        }
    else:
        indexed = index_accession(
            s3_client=s3_client,
            bucket=bucket,
            cik=cik,
            accession_number=accession_number,
            indexer=indexer,  # type: ignore[arg-type]
        )

    result: dict[str, Any] = {
        "mode": mode,
        "indexed_chunks": indexed["indexed_chunks"],
        "ticker": indexed["ticker"],
        "filing_date": indexed["filing_date"],
        "warehouse_uri": None,
    }
    if mode in {"index_emit", "emit_only"}:
        if retriever is None or extractor is None:
            raise ValueError("retriever and extractor required for emit modes")
        if wait_for_visibility and aoss_client is not None:
            wait_until_accession_searchable(
                search_client=aoss_client,
                index_name=getattr(aoss_client, "index_name", "sec-10k-chunks"),
                accession_number=accession_number,
            )
        emission, warehouse_uri = emit_for_filing(
            retriever=retriever,
            extractor=extractor,
            ticker=indexed["ticker"],
            cik=indexed["provenance"]["cik"],
            accession_number=accession_number,
            form=indexed["form"],
            filing_date=indexed["filing_date"],
            s3_client=s3_client,
            bucket=bucket,
            persist_warehouse=True,
        )
        result["warehouse_uri"] = warehouse_uri
        result["emission_ticker"] = emission.ticker.value
    return result


def main(argv: list[str] | None = None) -> int:
    """CLI entry for the Fargate index+emit worker."""
    parser = argparse.ArgumentParser(description="Fargate index+emit worker")
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--cik", required=True)
    parser.add_argument("--accession", required=True)
    parser.add_argument(
        "--mode",
        default="index_emit",
        choices=["index_emit", "index_only", "rebuild", "emit_only"],
    )
    args = parser.parse_args(argv)

    runtime = build_runtime(raw_bucket=args.bucket)
    result = run_index_emit(
        s3_client=runtime.s3_client,
        bucket=runtime.bucket,
        cik=args.cik,
        accession_number=args.accession,
        indexer=runtime.indexer,
        retriever=runtime.retriever,
        extractor=runtime.extractor,
        mode=args.mode,
        aoss_client=runtime.aoss_client,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
