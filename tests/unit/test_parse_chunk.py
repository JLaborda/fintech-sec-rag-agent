"""Section-aware chunking tests (T023)."""

from pathlib import Path

from sec_signals.parse.section_chunker import chunk_filing_text

ROOT = Path(__file__).resolve().parents[2]
SNIPPET = (ROOT / "fixtures/filings/sample_10k_snippet.txt").read_text()


def test_chunker_assigns_item_and_section_metadata() -> None:
    chunks = chunk_filing_text(
        SNIPPET,
        ticker="V",
        cik="0001403161",
        accession_number="0001403161-25-000001",
        form="10-K",
        filing_date="2025-11-15",
    )
    assert chunks
    assert all(c.filing_date.isoformat() == "2025-11-15" for c in chunks)
    items = {c.item for c in chunks}
    assert "Item 1" in items or "Item 1A" in items
    assert any("regulation" in c.text.lower() for c in chunks)
