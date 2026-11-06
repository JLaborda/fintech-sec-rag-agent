"""Per-factor top-k retrieval orchestration."""

from __future__ import annotations

from sec_signals.models.enums import DemoTicker, FactorId, FormType
from sec_signals.models.filing import Chunk
from sec_signals.retrieve.opensearch_client import OpenSearchClient
from sec_signals.retrieve.titan_embed import TitanEmbedClient

FACTOR_QUERIES: dict[FactorId, str] = {
    FactorId.REGULATORY_AND_LEGAL_RISK: "regulatory legal litigation compliance risk",
    FactorId.COMPETITIVE_POSITION: "competition competitive position market share brand network",
    FactorId.MANAGEMENT_TONE: "management discussion outlook tone confidence uncertainty",
    FactorId.DEMAND_AND_GROWTH_OUTLOOK: "demand growth revenue outlook customers volume",
    FactorId.OPERATIONAL_AND_SUPPLY_RISK: "operations supply chain vendors resilience disruption",
}


class FactorRetriever:
    def __init__(self, embedder: TitanEmbedClient, search: OpenSearchClient) -> None:
        self._embedder = embedder
        self._search = search

    def retrieve_for_factors(
        self,
        *,
        ticker: DemoTicker | str,
        accession_number: str,
        filing_date: str,
        form: FormType | str = FormType.TEN_K,
        cik: str = "0",
        k: int = 3,
    ) -> dict[FactorId, list[Chunk]]:
        ticker_value = ticker.value if isinstance(ticker, DemoTicker) else ticker
        form_value = form if isinstance(form, FormType) else FormType(form)
        out: dict[FactorId, list[Chunk]] = {}
        for factor_id, query in FACTOR_QUERIES.items():
            vector = self._embedder.embed(query)
            hits = self._search.knn_search(
                vector=vector,
                ticker=ticker_value,
                accession_number=accession_number,
                filing_date=filing_date,
                k=k,
            )
            out[factor_id] = [
                Chunk(
                    chunk_id=hit.chunk_id,
                    ticker=ticker_value,
                    cik=cik,
                    accession_number=accession_number,
                    form=form_value,
                    filing_date=filing_date,
                    section=hit.section,
                    item=hit.item,
                    text=hit.text,
                    char_start=hit.char_start,
                    char_end=hit.char_end,
                )
                for hit in hits
            ]
        return out
