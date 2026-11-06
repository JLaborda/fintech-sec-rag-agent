"""Rebuild derived vectors from the immutable lake."""

from __future__ import annotations

from typing import Any

from sec_signals.pipeline.index import index_accession
from sec_signals.retrieve.indexer import ChunkIndexer


def rebuild_accession(
    *,
    s3_client: Any,
    bucket: str,
    cik: str,
    accession_number: str,
    indexer: ChunkIndexer,
) -> dict[str, Any]:
    indexer.delete_accession(accession_number)
    return index_accession(
        s3_client=s3_client,
        bucket=bucket,
        cik=cik,
        accession_number=accession_number,
        indexer=indexer,
    )
