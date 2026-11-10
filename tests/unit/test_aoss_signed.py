"""AOSS SigV4 HTTP client (unit, no live account)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from sec_signals.retrieve.aoss_signed import AossSignedClient, build_aoss_client


class _FakeResponse:
    def __init__(self, payload: dict[str, Any] | None = None, status: int = 200) -> None:
        self._payload = payload if payload is not None else {}
        self.status_code = status
        self.text = json.dumps(self._payload) if payload is not None else ""

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


class _FakeSession:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.index_exists = False
        self.docs: dict[str, dict[str, Any]] = {}

    def request(  # noqa: ANN001
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        data: bytes | None = None,
        timeout: float | tuple[float, float] | None = None,
    ):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "data": data,
                "timeout": timeout,
            }
        )
        if method == "HEAD":
            return _FakeResponse(None, status=200 if self.index_exists else 404)
        if method == "PUT" and "/_doc/" not in url and "_search" not in url:
            self.index_exists = True
            return _FakeResponse({"acknowledged": True})
        if method == "POST" and url.rstrip("/").endswith("/_doc"):
            body = json.loads(data.decode("utf-8")) if data else {}
            doc_id = f"auto-{len(self.docs) + 1}"
            self.docs[doc_id] = body
            return _FakeResponse({"result": "created", "_id": doc_id})
        if method == "POST" and "_search" in url:
            body = json.loads(data.decode("utf-8")) if data else {}
            accession = None
            try:
                accession = body["query"]["term"]["accession_number"]
            except (KeyError, TypeError):
                accession = None
            hits = []
            for doc_id, src in self.docs.items():
                if accession is None or src.get("accession_number") == accession:
                    hits.append({"_id": doc_id, "_source": src, "_score": 1.0})
            return _FakeResponse({"hits": {"hits": hits}})
        if method == "DELETE" and "/_doc/" in url:
            doc_id = url.rsplit("/", 1)[-1]
            self.docs.pop(doc_id, None)
            return _FakeResponse({"result": "deleted"})
        return _FakeResponse({"result": "created"})


class _FakeCreds:
    access_key = "AKIATEST"
    secret_key = "secret"
    token = None

    def get_frozen_credentials(self) -> _FakeCreds:
        return self


def test_aoss_index_posts_without_custom_id_and_signs() -> None:
    session = _FakeSession()
    client = AossSignedClient(
        endpoint="https://abc.eu-west-1.aoss.amazonaws.com",
        region="eu-west-1",
        credentials=_FakeCreds(),
        http=session,
        index_name="sec-10k-chunks",
    )
    client.index(index="sec-10k-chunks", id="c1", body={"chunk_id": "c1", "text": "x"})
    index_calls = [c for c in session.calls if c["method"] == "POST" and c["url"].endswith("/_doc")]
    assert len(index_calls) == 1
    assert "/_doc/c1" not in index_calls[0]["url"]
    assert index_calls[0]["timeout"] is not None
    assert "X-Amz-Content-SHA256" in index_calls[0]["headers"]
    assert "Authorization" in index_calls[0]["headers"]

    hits = client.search(index="sec-10k-chunks", body={"query": {"match_all": {}}})
    assert hits["hits"]["hits"]
    search_calls = [c for c in session.calls if "_search" in c["url"]]
    assert all("Authorization" in c["headers"] for c in search_calls)


def test_aoss_delete_by_query_uses_search_then_delete() -> None:
    session = _FakeSession()
    client = AossSignedClient(
        endpoint="https://abc.eu-west-1.aoss.amazonaws.com",
        region="eu-west-1",
        credentials=_FakeCreds(),
        http=session,
        index_name="sec-10k-chunks",
    )
    client.index(
        index="sec-10k-chunks",
        id="ignored",
        body={"chunk_id": "c1", "accession_number": "0001", "text": "a"},
    )
    client.index(
        index="sec-10k-chunks",
        id="ignored",
        body={"chunk_id": "c2", "accession_number": "0002", "text": "b"},
    )
    client.delete_by_query(
        index="sec-10k-chunks",
        body={"query": {"term": {"accession_number": "0001"}}},
    )
    assert all(d.get("accession_number") != "0001" for d in session.docs.values())
    assert any(d.get("accession_number") == "0002" for d in session.docs.values())
    assert any(c["method"] == "DELETE" and "/_doc/" in c["url"] for c in session.calls)
    assert not any("_delete_by_query" in c["url"] for c in session.calls)


def test_ensure_index_creates_knn_mapping_when_missing() -> None:
    session = _FakeSession()
    client = AossSignedClient(
        endpoint="https://abc.eu-west-1.aoss.amazonaws.com",
        region="eu-west-1",
        credentials=_FakeCreds(),
        http=session,
        index_name="sec-10k-chunks",
    )
    client.ensure_index(dimension=1024)
    put_calls = [
        c
        for c in session.calls
        if c["method"] == "PUT" and c["url"].endswith("/sec-10k-chunks")
    ]
    assert len(put_calls) == 1
    body = json.loads(put_calls[0]["data"].decode("utf-8"))
    assert body["settings"]["index.knn"] is True
    assert body["mappings"]["properties"]["embedding"]["type"] == "knn_vector"
    assert body["mappings"]["properties"]["embedding"]["dimension"] == 1024


def test_build_aoss_client_keeps_refreshable_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Refreshing:
        access_key = "AKIATEST"
        secret_key = "secret"
        token = None
        frozen_calls = 0

        def get_frozen_credentials(self) -> _FakeCreds:
            self.frozen_calls += 1
            return _FakeCreds()

    refreshable = _Refreshing()

    class _Session:
        def get_credentials(self):  # noqa: ANN001
            return refreshable

    monkeypatch.setattr(
        "sec_signals.retrieve.aoss_signed.boto3.Session",
        lambda **kwargs: _Session(),
    )
    session = _FakeSession()
    client = build_aoss_client(
        endpoint="https://abc.eu-west-1.aoss.amazonaws.com",
        region="eu-west-1",
        http=session,
    )
    client.index(index="sec-10k-chunks", id="c1", body={"chunk_id": "c1"})
    client.search(index="sec-10k-chunks", body={"query": {"match_all": {}}})
    assert refreshable.frozen_calls >= 2
