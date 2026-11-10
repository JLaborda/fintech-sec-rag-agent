"""Ingest pipeline: EDGAR → immutable S3 raw lake (mocked)."""

from __future__ import annotations

from typing import Any

from sec_signals.pipeline.ingest import ingest_tickers


class _MemS3:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes | str, **kwargs):  # noqa: ANN003
        if isinstance(Body, str):
            Body = Body.encode("utf-8")
        self.objects[f"s3://{Bucket}/{Key}"] = Body

    def get_object(self, *, Bucket: str, Key: str):  # noqa: ANN003
        key = f"s3://{Bucket}/{Key}"
        if key not in self.objects:
            raise Exception("NoSuchKey")

        class _Body:
            def read(self_inner):  # noqa: ANN001
                return self.objects[key]

        return {"Body": _Body()}


class _FakeEdgar:
    def latest_10k_for_ticker(self, ticker):  # noqa: ANN001
        return {
            "ticker": str(ticker.value if hasattr(ticker, "value") else ticker),
            "cik": "0001403161",
            "accession_number": "0001403161-25-000001",
            "form": "10-K",
            "filing_date": "2025-11-15",
            "primary_document": "v-20250930.htm",
        }

    def fetch_primary_document(self, filing: dict[str, Any]) -> bytes:
        return b"ITEM 1A. RISK FACTORS\nRegulation applies.\n"


def test_ingest_tickers_writes_raw_and_provenance() -> None:
    s3 = _MemS3()
    order: list[str] = []
    original_put = s3.put_object

    def tracking_put(**kwargs):  # noqa: ANN003
        order.append(kwargs["Key"])
        return original_put(**kwargs)

    s3.put_object = tracking_put  # type: ignore[method-assign]
    results = ingest_tickers(
        ["V"],
        edgar=_FakeEdgar(),
        s3_client=s3,
        bucket="lake",
    )
    assert len(results) == 1
    assert results[0]["ticker"] == "V"
    assert results[0]["status"] == "ok"
    assert results[0]["uri"].startswith("s3://lake/raw/edgar/")
    assert any(k.endswith("provenance.json") for k in s3.objects)
    assert any(k.endswith("v-20250930.htm") for k in s3.objects)
    # Sidecar-first so SFN primary-doc trigger sees provenance already present.
    assert order[0].endswith("provenance.json")
    assert any(k.endswith("v-20250930.htm") for k in order[1:])


def test_ingest_continues_after_per_ticker_failure() -> None:
    s3 = _MemS3()

    class _PartialEdgar(_FakeEdgar):
        def latest_10k_for_ticker(self, ticker):  # noqa: ANN001
            if str(getattr(ticker, "value", ticker)) == "MA":
                raise RuntimeError("edgar down")
            return super().latest_10k_for_ticker(ticker)

    results = ingest_tickers(
        ["V", "MA"],
        edgar=_PartialEdgar(),
        s3_client=s3,
        bucket="lake",
    )
    assert results[0]["status"] == "ok"
    assert results[1]["status"] == "error"
    assert "edgar down" in results[1]["error"]
