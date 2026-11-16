"""T003 CA-1: concurrent embed + OpenSearch bulk in ChunkIndexer."""

from __future__ import annotations

import threading
import time
from datetime import date
from typing import Any

from sec_signals.models.enums import DemoTicker, FormType
from sec_signals.models.filing import Chunk
from sec_signals.retrieve.indexer import ChunkIndexer


class _FakeEmbedder:
    """Records peak in-flight embed calls to prove concurrency."""

    def __init__(self, *, hold_seconds: float = 0.05) -> None:
        self._hold_seconds = hold_seconds
        self._lock = threading.Lock()
        self.in_flight = 0
        self.peak_in_flight = 0
        self.call_count = 0

    def embed(self, text: str) -> list[float]:
        _ = text
        with self._lock:
            self.call_count += 1
            self.in_flight += 1
            self.peak_in_flight = max(self.peak_in_flight, self.in_flight)
        time.sleep(self._hold_seconds)
        with self._lock:
            self.in_flight -= 1
        return [0.0] * 1024


class _FakeSearchClient:
    def __init__(self) -> None:
        self.index_calls: list[dict[str, Any]] = []
        self.bulk_calls: list[list[dict[str, Any]]] = []

    def index(self, *, index: str, id: str, body: dict[str, Any]) -> Any:
        self.index_calls.append({"index": index, "id": id, "body": body})
        return {"result": "created"}

    def bulk(self, *, body: list[dict[str, Any]]) -> Any:
        self.bulk_calls.append(list(body))
        return {"errors": False, "items": []}

    def delete_by_query(self, *, index: str, body: dict[str, Any]) -> Any:
        _ = (index, body)
        return {"deleted": 0}


def _chunks(n: int) -> list[Chunk]:
    return [
        Chunk(
            chunk_id=f"c{i}",
            ticker=DemoTicker.V,
            cik="0001403161",
            accession_number="0001403161-25-000001",
            form=FormType.TEN_K,
            filing_date=date(2025, 11, 15),
            section="Item 1A",
            item="1A",
            text=f"risk factor text {i}",
            char_start=i * 10,
            char_end=i * 10 + 9,
            embedding=None,
        )
        for i in range(n)
    ]


def _bulk_doc_count(bulk_body: list[dict[str, Any]]) -> int:
    """Count documents in an OpenSearch-style bulk body (action, doc, ...)."""
    return sum(1 for i, item in enumerate(bulk_body) if i % 2 == 1)


def test_concurrent_embed_and_bulk() -> None:
    embedder = _FakeEmbedder()
    client = _FakeSearchClient()
    indexer = ChunkIndexer(
        embedder=embedder,  # type: ignore[arg-type]
        client=client,
        embed_concurrency=4,
        opensearch_bulk_size=3,
    )

    count = indexer.upsert_chunks(_chunks(8))

    assert count == 8
    assert embedder.call_count == 8
    assert embedder.peak_in_flight > 1

    assert client.bulk_calls, "expected OpenSearch bulk writes, not only per-doc index"
    assert all(_bulk_doc_count(body) <= 3 for body in client.bulk_calls)
    assert sum(_bulk_doc_count(body) for body in client.bulk_calls) == 8
    # Prefer bulk path for this CA; sequential per-doc index alone must not satisfy it.
    assert len(client.index_calls) == 0
