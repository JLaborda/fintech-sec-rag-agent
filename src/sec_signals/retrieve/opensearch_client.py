"""OpenSearch Serverless retrieve client (RAG only)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RetrievedHit:
    chunk_id: str
    text: str
    section: str
    item: str
    ticker: str
    accession_number: str
    filing_date: str
    score: float
    char_start: int | None = None
    char_end: int | None = None


class OpenSearchClient:
    """Thin wrapper; accepts an injected low-level client for tests."""

    def __init__(self, client: Any, *, index_name: str = "sec-10k-chunks") -> None:
        self._client = client
        self.index_name = index_name

    def knn_search(
        self,
        *,
        vector: list[float],
        ticker: str,
        accession_number: str | None = None,
        filing_date: str | None = None,
        k: int = 5,
    ) -> list[RetrievedHit]:
        filters: list[dict[str, Any]] = [{"term": {"ticker": ticker}}]
        if accession_number:
            filters.append({"term": {"accession_number": accession_number}})
        if filing_date:
            filters.append({"term": {"filing_date": filing_date}})
        body = {
            "size": k,
            "query": {
                "bool": {
                    "filter": filters,
                    "must": [
                        {
                            "knn": {
                                "embedding": {
                                    "vector": vector,
                                    "k": k,
                                }
                            }
                        }
                    ],
                }
            },
        }
        response = self._client.search(index=self.index_name, body=body)
        hits: list[RetrievedHit] = []
        for hit in response.get("hits", {}).get("hits", []):
            src = hit.get("_source", {})
            hits.append(
                RetrievedHit(
                    chunk_id=src["chunk_id"],
                    text=src["text"],
                    section=src["section"],
                    item=src["item"],
                    ticker=src["ticker"],
                    accession_number=src["accession_number"],
                    filing_date=src["filing_date"],
                    score=float(hit.get("_score") or 0.0),
                    char_start=src.get("char_start"),
                    char_end=src.get("char_end"),
                )
            )
        return hits
