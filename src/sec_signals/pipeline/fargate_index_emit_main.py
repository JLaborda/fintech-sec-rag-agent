"""Fargate entry: primary index + emit + warehouse (or index-only rebuild)."""

from __future__ import annotations

import argparse
import json
from typing import Any, Protocol

from sec_signals.aws.runtime import build_runtime
from sec_signals.pipeline.emit import emit_for_filing
from sec_signals.pipeline.index import index_accession
from sec_signals.pipeline.reindex import rebuild_accession


class _Indexer(Protocol):
    def upsert_chunks(self, chunks): ...  # noqa: ANN001


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
) -> dict[str, Any]:
    if mode == "rebuild":
        indexed = rebuild_accession(
            s3_client=s3_client,
            bucket=bucket,
            cik=cik,
            accession_number=accession_number,
            indexer=indexer,  # type: ignore[arg-type]
        )
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

    runtime = build_runtime()
    bucket = args.bucket or runtime.bucket
    result = run_index_emit(
        s3_client=runtime.s3_client,
        bucket=bucket,
        cik=args.cik,
        accession_number=args.accession,
        indexer=runtime.indexer,
        retriever=runtime.retriever,
        extractor=runtime.extractor,
        mode=args.mode,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
