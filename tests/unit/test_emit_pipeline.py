"""Emit + batch emit library tests (T020–T022)."""

from __future__ import annotations

from datetime import date

from sec_signals.models.enums import DemoTicker, FactorId, FactorStatus, FormType
from sec_signals.models.filing import Chunk
from sec_signals.pipeline.batch_emit import FilingRef, batch_emit
from sec_signals.pipeline.emit import emit_for_filing


class _FakeRetriever:
    def retrieve_for_factors(self, **kwargs):  # noqa: ANN003
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


def test_emit_persists_warehouse_parquet() -> None:
    s3 = _FakeS3()
    emission, uri = emit_for_filing(
        retriever=_FakeRetriever(),
        extractor=_FakeExtractor(),
        ticker="V",
        cik="0001403161",
        accession_number="0001403161-25-000001",
        form="10-K",
        filing_date="2025-11-15",
        s3_client=s3,
        bucket="demo-lake",
        persist_warehouse=True,
    )
    assert emission.ticker is DemoTicker.V
    assert uri and uri.startswith("s3://demo-lake/curated/signals/")
    assert any("filing_date=2025-11-15" in key for key in s3.objects)
    ok = next(f for f in emission.factors if f.status is FactorStatus.OK)
    assert ok.polarity == -0.2


def test_batch_emit_isolates_per_ticker_errors() -> None:
    def resolve(ticker: DemoTicker) -> FilingRef:
        if ticker is DemoTicker.MA:
            raise RuntimeError("no filing")
        return FilingRef(
            ticker=ticker,
            cik="0001403161",
            accession_number="0001403161-25-000001",
            form="10-K",
            filing_date="2025-11-15",
        )

    s3 = _FakeS3()
    results = batch_emit(
        ["V", "MA"],
        resolve_latest=resolve,
        retriever=_FakeRetriever(),
        extractor=_FakeExtractor(),
        s3_client=s3,
        bucket="demo-lake",
    )
    assert results[0].status == "emitted"
    assert results[1].status == "error"
    assert results[1].error_message == "no filing"
