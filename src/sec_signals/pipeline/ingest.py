"""Ingest latest 10-K/10-K/A filings into the immutable S3 raw lake."""

from __future__ import annotations

from typing import Any, Protocol

from sec_signals.lake.raw import write_raw_filing
from sec_signals.models.enums import DemoTicker


class EdgarLike(Protocol):
    def latest_10k_for_ticker(self, ticker: DemoTicker | str) -> dict[str, Any]: ...
    def fetch_primary_document(self, filing: dict[str, Any]) -> bytes: ...


def ingest_tickers(
    tickers: list[str | DemoTicker],
    *,
    edgar: EdgarLike,
    s3_client: Any,
    bucket: str,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for raw in tickers:
        ticker = raw if isinstance(raw, DemoTicker) else DemoTicker(raw.strip().upper())
        filing = edgar.latest_10k_for_ticker(ticker)
        form = filing["form"]
        if form not in {"10-K", "10-K/A"}:
            raise ValueError(f"refusing non-10-K form for {ticker.value}: {form}")
        raw_bytes = edgar.fetch_primary_document(filing)
        cik = filing["cik"]
        accession = filing["accession_number"]
        primary = filing["primary_document"]
        source_urls = [
            (
                "https://www.sec.gov/Archives/edgar/data/"
                f"{str(cik).lstrip('0') or '0'}/{accession.replace('-', '')}/{primary}"
            )
        ]
        uri = write_raw_filing(
            s3_client=s3_client,
            bucket=bucket,
            ticker=ticker.value,
            cik=cik,
            accession_number=accession,
            form=form,
            filing_date=filing["filing_date"],
            primary_document=primary,
            raw_bytes=raw_bytes,
            source_urls=source_urls,
        )
        results.append(
            {
                "ticker": ticker.value,
                "cik": cik,
                "accession_number": accession,
                "form": form,
                "filing_date": filing["filing_date"],
                "uri": uri,
            }
        )
    return results
