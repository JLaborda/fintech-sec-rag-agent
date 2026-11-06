"""AOSS upsert indexer (derived vectors)."""

from __future__ import annotations

from typing import Any, Protocol

from sec_signals.models.filing import Chunk
from sec_signals.retrieve.titan_embed import TitanEmbedClient


class SearchIndexerClient(Protocol):
    def index(self, *, index: str, id: str, body: dict[str, Any]) -> Any: ...
    def delete_by_query(self, *, index: str, body: dict[str, Any]) -> Any: ...


class ChunkIndexer:
    def __init__(
        self,
        *,
        embedder: TitanEmbedClient,
        client: SearchIndexerClient,
        index_name: str = "sec-10k-chunks",
    ) -> None:
        self._embedder = embedder
        self._client = client
        self.index_name = index_name

    def upsert_chunks(self, chunks: list[Chunk]) -> int:
        count = 0
        for chunk in chunks:
            embedding = chunk.embedding or self._embedder.embed(chunk.text)
            body = {
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
            self._client.index(index=self.index_name, id=chunk.chunk_id, body=body)
            count += 1
        return count

    def delete_accession(self, accession_number: str) -> None:
        self._client.delete_by_query(
            index=self.index_name,
            body={"query": {"term": {"accession_number": accession_number}}},
        )
