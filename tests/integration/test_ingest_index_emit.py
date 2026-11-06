"""Integration: ingest → index → emit → warehouse (T025)."""

from __future__ import annotations

from datetime import date

from sec_signals.lake.raw import write_raw_filing
from sec_signals.models.enums import FactorId, FormType
from sec_signals.models.filing import Chunk
from sec_signals.parse.section_chunker import chunk_filing_text
from sec_signals.pipeline.emit import emit_for_filing
from sec_signals.pipeline.fargate_index_emit_main import run_index_emit
from sec_signals.pipeline.s3_event import parse_raw_s3_event


class _MemS3:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes | str, **kwargs):  # noqa: ANN003
        if isinstance(Body, str):
            Body = Body.encode("utf-8")
        self.objects[f"s3://{Bucket}/{Key}"] = Body

    def get_object(self, *, Bucket: str, Key: str):  # noqa: ANN003
        body = self.objects[f"s3://{Bucket}/{Key}"]

        class _Body:
            def read(self_inner):  # noqa: ANN001
                return body

        return {"Body": _Body()}


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


class _FakeIndexer:
    def __init__(self) -> None:
        self.upserts = 0

    def upsert_chunks(self, chunks):  # noqa: ANN001
        self.upserts += len(chunks)
        return len(chunks)


def test_raw_write_and_s3_event_parse() -> None:
    s3 = _MemS3()
    uri = write_raw_filing(
        s3_client=s3,
        bucket="lake",
        ticker="V",
        cik="0001403161",
        accession_number="0001403161-25-000001",
        form="10-K",
        filing_date="2025-11-15",
        primary_document="primary.htm",
        raw_bytes=b"ITEM 1A. RISK FACTORS\nWe are subject to extensive government regulation.\n",
        source_urls=["https://www.sec.gov/example"],
    )
    assert uri.startswith("s3://lake/raw/edgar/0001403161/0001403161-25-000001/")
    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "lake"},
                    "object": {
                        "key": "raw/edgar/0001403161/0001403161-25-000001/primary.htm"
                    },
                }
            }
        ]
    }
    parsed = parse_raw_s3_event(event)
    assert parsed["bucket"] == "lake"
    assert parsed["cik"] == "0001403161"
    assert parsed["accession_number"] == "0001403161-25-000001"


def test_index_emit_writes_warehouse() -> None:
    s3 = _MemS3()
    write_raw_filing(
        s3_client=s3,
        bucket="lake",
        ticker="V",
        cik="0001403161",
        accession_number="0001403161-25-000001",
        form="10-K",
        filing_date="2025-11-15",
        primary_document="primary.htm",
        raw_bytes=b"ITEM 1A. RISK FACTORS\nWe are subject to extensive government regulation.\n",
        source_urls=["https://www.sec.gov/example"],
    )
    indexer = _FakeIndexer()
    result = run_index_emit(
        s3_client=s3,
        bucket="lake",
        cik="0001403161",
        accession_number="0001403161-25-000001",
        indexer=indexer,
        retriever=_FakeRetriever(),
        extractor=_FakeExtractor(),
        mode="index_emit",
    )
    assert result["indexed_chunks"] >= 1
    assert result["warehouse_uri"]
    assert any("curated/signals" in k for k in s3.objects)
