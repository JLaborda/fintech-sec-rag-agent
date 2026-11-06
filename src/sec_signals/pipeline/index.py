"""Index pipeline: chunk → embed → AOSS upsert."""

from __future__ import annotations

from typing import Any

from sec_signals.lake.raw import load_primary_text, load_provenance
from sec_signals.parse.section_chunker import chunk_filing_text
from sec_signals.retrieve.indexer import ChunkIndexer


def index_accession(
    *,
    s3_client: Any,
    bucket: str,
    cik: str,
    accession_number: str,
    indexer: ChunkIndexer,
) -> dict[str, Any]:
    provenance = load_provenance(s3_client, bucket, cik, accession_number)
    text = load_primary_text(
        s3_client,
        bucket,
        cik,
        accession_number,
        provenance["primary_document"],
    )
    chunks = chunk_filing_text(
        text,
        ticker=provenance["ticker"],
        cik=provenance["cik"],
        accession_number=provenance["accession_number"],
        form=provenance["form"],
        filing_date=provenance["filing_date"],
    )
    indexed = indexer.upsert_chunks(chunks)
    return {
        "ticker": provenance["ticker"],
        "cik": cik,
        "accession_number": accession_number,
        "filing_date": provenance["filing_date"],
        "form": provenance["form"],
        "indexed_chunks": indexed,
        "chunks": chunks,
        "provenance": provenance,
    }
