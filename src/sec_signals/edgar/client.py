"""EDGAR helpers: latest 10-K/10-K/A selection and fetch."""

from __future__ import annotations

import time
from typing import Any

import httpx

from sec_signals.edgar.universe import cik_for_ticker
from sec_signals.models.enums import DemoTicker

ALLOWED_FORMS = {"10-K", "10-K/A"}

# SEC fair-access: stay under ~10 req/s. Borrowed from SmartWealthAI sec_client (~8/s).
SEC_THROTTLE_SEC = 0.12


def select_latest_filing(filings: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [f for f in filings if f.get("form") in ALLOWED_FORMS]
    if not candidates:
        raise ValueError("no 10-K or 10-K/A filings available")
    candidates.sort(key=lambda f: (f["filing_date"], f["accession_number"]))
    return candidates[-1]


class EdgarClient:
    def __init__(
        self,
        *,
        user_agent: str,
        client: httpx.Client | None = None,
        throttle_sec: float = SEC_THROTTLE_SEC,
    ) -> None:
        if not user_agent:
            raise ValueError("SEC EDGAR User-Agent is required")
        self.user_agent = user_agent
        self._client = client or httpx.Client(timeout=30.0)
        self._throttle_sec = throttle_sec
        self._last_request_at = 0.0

    def _headers(self) -> dict[str, str]:
        return {"User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate"}

    def _throttle(self) -> None:
        if self._throttle_sec <= 0:
            return
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._throttle_sec:
            time.sleep(self._throttle_sec - elapsed)
        self._last_request_at = time.monotonic()

    def _get(self, url: str) -> httpx.Response:
        self._throttle()
        response = self._client.get(url, headers=self._headers())
        response.raise_for_status()
        return response

    def company_submissions(self, cik: str) -> dict[str, Any]:
        padded = cik.zfill(10)
        url = f"https://data.sec.gov/submissions/CIK{padded}.json"
        return self._get(url).json()

    def latest_10k_for_ticker(self, ticker: DemoTicker | str) -> dict[str, Any]:
        ticker_enum = ticker if isinstance(ticker, DemoTicker) else DemoTicker(ticker)
        cik = cik_for_ticker(ticker_enum)
        data = self.company_submissions(cik)
        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        primaries = recent.get("primaryDocument", [])
        filings = []
        for form, filing_date, accession, primary in zip(
            forms, dates, accessions, primaries, strict=False
        ):
            filings.append(
                {
                    "form": form,
                    "filing_date": filing_date,
                    "accession_number": accession,
                    "primary_document": primary,
                    "ticker": ticker_enum.value,
                    "cik": cik,
                }
            )
        latest = select_latest_filing(filings)
        latest["ticker"] = ticker_enum.value
        latest["cik"] = cik
        return latest

    def fetch_primary_document(self, filing: dict[str, Any]) -> bytes:
        """Download the primary 10-K/10-K/A document bytes from EDGAR archives."""
        cik = str(filing["cik"]).lstrip("0") or "0"
        accession_nodash = str(filing["accession_number"]).replace("-", "")
        primary = filing["primary_document"]
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{primary}"
        return self._get(url).content
