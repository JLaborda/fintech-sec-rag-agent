"""Filing/Chunk models (T007)."""

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from sec_signals.models.enums import FormType
from sec_signals.models.filing import Chunk, Filing


def test_filing_requires_filing_date() -> None:
    filing = Filing(
        ticker="MA",
        cik="0001141391",
        accession_number="0001141391-25-000001",
        form=FormType.TEN_K,
        filing_date=date(2025, 2, 1),
        source_urls=["https://www.sec.gov/Archives/edgar/data/1141391/000114139125000001/"],
        raw_s3_uri="s3://lake/raw/edgar/0001141391/0001141391-25-000001/primary.htm",
        primary_document="primary.htm",
        ingested_at=datetime(2025, 2, 2, tzinfo=timezone.utc),
    )
    assert filing.filing_date.isoformat() == "2025-02-01"


def test_chunk_requires_section_item_and_filing_date() -> None:
    chunk = Chunk(
        chunk_id="c1",
        ticker="MA",
        cik="0001141391",
        accession_number="0001141391-25-000001",
        form=FormType.TEN_K_A,
        filing_date=date(2025, 3, 1),
        section="MD&A",
        item="Item 7",
        text="Revenue grew.",
    )
    assert chunk.item == "Item 7"


def test_chunk_rejects_wrong_embedding_dim() -> None:
    with pytest.raises(ValidationError):
        Chunk(
            chunk_id="c1",
            ticker="MA",
            cik="0001141391",
            accession_number="0001141391-25-000001",
            form=FormType.TEN_K,
            filing_date=date(2025, 3, 1),
            section="MD&A",
            item="Item 7",
            text="Revenue grew.",
            embedding=[0.1, 0.2],
        )
