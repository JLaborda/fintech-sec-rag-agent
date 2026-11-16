"""AOSS upsert indexer (derived vectors)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Protocol

from sec_signals.config import DEFAULT_EMBED_CONCURRENCY, DEFAULT_OPENSEARCH_BULK_SIZE
from sec_signals.models.filing import Chunk
from sec_signals.retrieve.titan_embed import TitanEmbedClient


class SearchIndexerClient(Protocol):
    def index(self, *, index: str, id: str, body: dict[str, Any]) -> Any: ...
    def bulk(self, *, body: list[dict[str, Any]]) -> Any: ...
    def delete_by_query(self, *, index: str, body: dict[str, Any]) -> Any: ...


class ChunkIndexer:
    def __init__(
        self,
        *,
        embedder: TitanEmbedClient,
        client: SearchIndexerClient,
        index_name: str = "sec-10k-chunks",
        embed_concurrency: int = DEFAULT_EMBED_CONCURRENCY,
        opensearch_bulk_size: int = DEFAULT_OPENSEARCH_BULK_SIZE,
    ) -> None:
        if embed_concurrency < 1:
            raise ValueError("embed_concurrency must be >= 1")
        if opensearch_bulk_size < 1:
            raise ValueError("opensearch_bulk_size must be >= 1")
        self._embedder = embedder
        self._client = client
        self.index_name = index_name
        self._embed_concurrency = embed_concurrency
        self._opensearch_bulk_size = opensearch_bulk_size

    def _doc_body(self, chunk: Chunk, embedding: list[float]) -> dict[str, Any]:
        return {
            "chunk_id": chunk.chunk_id,
            "ticker": chunk.ticker.value,
            "cik": chunk.cik,
            "accession_number": chunk.accession_number,
            "form": chunk.form.value,
            "filing_date": chunk.filing_date.isoformat(),
            "section": chunk.section,
            "item": chunk.item,
            "text": chunk.text,
            "char_start": chunk.char_start,
            "char_end": chunk.char_end,
            "embedding": embedding,
        }

    def _embedding_for(self, chunk: Chunk) -> list[float]:
        if chunk.embedding is not None:
            return chunk.embedding
        return self._embedder.embed(chunk.text)

    def upsert_chunks(self, chunks: list[Chunk]) -> int:
        if not chunks:
            return 0

        with ThreadPoolExecutor(max_workers=self._embed_concurrency) as pool:
            embeddings = list(pool.map(self._embedding_for, chunks))

        operations: list[dict[str, Any]] = []
        written = 0
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            operations.append({"index": {"_index": self.index_name, "_id": chunk.chunk_id}})
            operations.append(self._doc_body(chunk, embedding))
            if len(operations) // 2 >= self._opensearch_bulk_size:
                self._client.bulk(body=operations)
                written += len(operations) // 2
                operations = []
        if operations:
            self._client.bulk(body=operations)
            written += len(operations) // 2
        return written

    def delete_accession(self, accession_number: str) -> None:
        self._client.delete_by_query(
            index=self.index_name,
            body={"query": {"term": {"accession_number": accession_number}}},
        )
