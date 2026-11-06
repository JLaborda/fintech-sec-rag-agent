"""EDGAR primary document fetch (mocked httpx)."""

from __future__ import annotations

from sec_signals.edgar.client import EdgarClient


class _Resp:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None


class _Http:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def get(self, url: str, headers=None):  # noqa: ANN001
        self.urls.append(url)
        return _Resp(b"<html>10-K</html>")


def test_fetch_primary_document_builds_archive_url() -> None:
    http = _Http()
    client = EdgarClient(user_agent="Demo contact@example.com", client=http)  # type: ignore[arg-type]
    body = client.fetch_primary_document(
        {
            "cik": "0001403161",
            "accession_number": "0001403161-25-000001",
            "primary_document": "v.htm",
        }
    )
    assert body == b"<html>10-K</html>"
    assert "www.sec.gov/Archives/edgar/data/1403161/000140316125000001/v.htm" in http.urls[0]
