"""API contract shape tests for secondary re-emit (T032)."""

from __future__ import annotations

from sec_signals.api.handlers import handle_batch_emit, handle_health
from sec_signals.models.enums import DemoTicker, FactorId, FormType
from sec_signals.models.filing import Chunk
from sec_signals.pipeline.batch_emit import FilingRef


class _FakeRetriever:
    def retrieve_for_factors(self, **kwargs):  # noqa: ANN003
        from datetime import date

        chunk = Chunk(
            chunk_id="c1",
            ticker=kwargs["ticker"],
            cik=kwargs["cik"],
            accession_number=kwargs["accession_number"],
            form=FormType.TEN_K,
            filing_date=date.fromisoformat(kwargs["filing_date"]),
            section="Risk Factors",
            item="Item 1A",
            text="We are subject to extensive government regulation.",
        )
        return {fid: [chunk] for fid in FactorId}


class _FakeExtractor:
    def extract(self, chunks_by_factor):  # noqa: ANN001
        factors = []
        for i, fid in enumerate(FactorId):
            if i == 0:
                factors.append(
                    {
                        "factor_id": fid.value,
                        "status": "ok",
                        "polarity": -0.2,
                        "conviction": 0.6,
                        "citation": {
                            "section": "Risk Factors",
                            "item": "Item 1A",
                            "quote": "We are subject to extensive government regulation.",
                        },
                        "reasoning": "Regulatory disclosure supports mild negative polarity.",
                    }
                )
            else:
                factors.append(
                    {
                        "factor_id": fid.value,
                        "status": "insufficient_evidence",
                        "reasoning": f"No evidence for {fid.value}.",
                    }
                )
        return {"factors": factors, "key_events": []}


class _FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes) -> None:
        self.objects[f"{Bucket}/{Key}"] = Body


def test_health() -> None:
    assert handle_health() == {"status": "ok"}


def test_batch_emit_response_shape() -> None:
    def resolve(ticker: DemoTicker) -> FilingRef:
        return FilingRef(
            ticker=ticker,
            cik="0001403161",
            accession_number="0001403161-25-000001",
            form="10-K",
            filing_date="2025-11-15",
        )

    s3 = _FakeS3()
    response, status = handle_batch_emit(
        {"tickers": ["V"], "include_key_events": True},
        resolve_latest=resolve,
        retriever=_FakeRetriever(),
        extractor=_FakeExtractor(),
        s3_client=s3,
        bucket="lake",
    )
    assert status == 200
    assert "disclaimer" in response
    assert response["results"][0]["status"] == "emitted"
    assert response["results"][0]["warehouse_uri"]
    assert response["results"][0]["emission"]["factor_schema_version"] == "0.1.0"


def test_batch_emit_rejects_unknown_ticker() -> None:
    response, status = handle_batch_emit(
        {"tickers": ["AAPL"]},
        resolve_latest=lambda t: None,  # type: ignore[arg-type,return-value]
        retriever=_FakeRetriever(),
        extractor=_FakeExtractor(),
        s3_client=_FakeS3(),
        bucket="lake",
    )
    assert status == 400
    assert response["code"] == "invalid_request"
