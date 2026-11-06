"""Latest 10-K / 10-K/A selection (T024)."""

from sec_signals.edgar.client import select_latest_filing


def test_select_latest_prefers_newer_filing_date() -> None:
    filings = [
        {
            "form": "10-K",
            "filing_date": "2023-11-01",
            "accession_number": "0001",
            "primary_document": "a.htm",
        },
        {
            "form": "10-K/A",
            "filing_date": "2024-12-01",
            "accession_number": "0002",
            "primary_document": "b.htm",
        },
        {
            "form": "10-Q",
            "filing_date": "2025-01-01",
            "accession_number": "0003",
            "primary_document": "c.htm",
        },
    ]
    latest = select_latest_filing(filings)
    assert latest["form"] == "10-K/A"
    assert latest["accession_number"] == "0002"


def test_select_latest_tie_break_newest_accession() -> None:
    filings = [
        {
            "form": "10-K",
            "filing_date": "2024-01-01",
            "accession_number": "000100",
            "primary_document": "a.htm",
        },
        {
            "form": "10-K",
            "filing_date": "2024-01-01",
            "accession_number": "000200",
            "primary_document": "b.htm",
        },
    ]
    latest = select_latest_filing(filings)
    assert latest["accession_number"] == "000200"
