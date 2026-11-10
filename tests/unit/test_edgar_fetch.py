"""EDGAR primary document fetch (mocked httpx)."""

from __future__ import annotations

import pytest

from sec_signals.edgar.client import EdgarClient


class _Resp:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {}


class _Http:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def get(self, url: str, headers=None):  # noqa: ANN001
        self.urls.append(url)
        return _Resp(b"<html>10-K</html>")


def test_fetch_primary_document_builds_archive_url() -> None:
    http = _Http()
    client = EdgarClient(
        user_agent="Demo contact@example.com",
        client=http,  # type: ignore[arg-type]
        throttle_sec=0,
    )
    body = client.fetch_primary_document(
        {
            "cik": "0001403161",
            "accession_number": "0001403161-25-000001",
            "primary_document": "v.htm",
        }
    )
    assert body == b"<html>10-K</html>"
    assert "www.sec.gov/Archives/edgar/data/1403161/000140316125000001/v.htm" in http.urls[0]


def test_throttle_sleeps_between_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("sec_signals.edgar.client.time.sleep", sleeps.append)
    # First request: large elapsed → no sleep. Second: 0.05s gap → sleep 0.07.
    ticks = iter([100.0, 100.0, 100.05, 100.05])
    monkeypatch.setattr("sec_signals.edgar.client.time.monotonic", lambda: next(ticks))

    http = _Http()
    client = EdgarClient(
        user_agent="Demo contact@example.com",
        client=http,  # type: ignore[arg-type]
        throttle_sec=0.12,
    )
    filing = {
        "cik": "0001403161",
        "accession_number": "0001403161-25-000001",
        "primary_document": "v.htm",
    }
    client.fetch_primary_document(filing)
    client.fetch_primary_document(filing)
    assert sleeps == [pytest.approx(0.07)]
