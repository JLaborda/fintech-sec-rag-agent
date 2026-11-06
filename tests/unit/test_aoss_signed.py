"""AOSS SigV4 HTTP client (unit, no live account)."""

from __future__ import annotations

import json
from typing import Any

from sec_signals.retrieve.aoss_signed import AossSignedClient


class _FakeResponse:
    def __init__(self, payload: dict[str, Any], status: int = 200) -> None:
        self._payload = payload
        self.status_code = status
        self.text = json.dumps(payload)

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


class _FakeSession:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def request(self, method: str, url: str, *, headers: dict[str, str], data: bytes | None = None):  # noqa: ANN001
        self.calls.append({"method": method, "url": url, "headers": headers, "data": data})
        if method == "POST" and "_search" in url:
            return _FakeResponse(
                {
                    "hits": {
                        "hits": [
                            {
                                "_score": 1.2,
                                "_source": {
                                    "chunk_id": "c1",
                                    "text": "hello",
                                    "section": "Risk Factors",
                                    "item": "Item 1A",
                                    "ticker": "V",
                                    "accession_number": "0001",
                                    "filing_date": "2025-01-01",
                                },
                            }
                        ]
                    }
                }
            )
        return _FakeResponse({"result": "created"})


class _FakeCreds:
    access_key = "AKIATEST"
    secret_key = "secret"
    token = None


def test_aoss_index_and_search_signed(monkeypatch: Any) -> None:
    session = _FakeSession()
    client = AossSignedClient(
        endpoint="https://abc.eu-west-1.aoss.amazonaws.com",
        region="eu-west-1",
        credentials=_FakeCreds(),
        http=session,
        index_name="sec-10k-chunks",
    )
    client.index(index="sec-10k-chunks", id="c1", body={"chunk_id": "c1", "text": "x"})
    assert any(c["method"] == "PUT" for c in session.calls)

    hits = client.search(index="sec-10k-chunks", body={"query": {"match_all": {}}})
    assert hits["hits"]["hits"][0]["_source"]["chunk_id"] == "c1"
    assert any(
        "Authorization" in c["headers"] or "X-Amz-Date" in c["headers"]
        for c in session.calls
    )
