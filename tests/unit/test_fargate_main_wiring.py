"""Fargate main must wire boto3/AOSS/Bedrock and call run_index_emit."""

from __future__ import annotations

import json
from typing import Any

from sec_signals.pipeline import fargate_index_emit_main as mod


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


def test_fargate_main_runs_index_emit(monkeypatch: Any, capsys: Any) -> None:
    from sec_signals.lake.raw import write_raw_filing

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

    class _Indexer:
        def upsert_chunks(self, chunks):  # noqa: ANN001
            return len(chunks)

    class _Runtime:
        s3_client = s3
        bucket = "lake"
        indexer = _Indexer()
        retriever = object()
        extractor = object()
        aoss_client = object()

    class _Emission:
        ticker = type("T", (), {"value": "V"})()

    emit_kwargs: dict[str, Any] = {}

    def fake_emit(**kwargs):  # noqa: ANN003
        emit_kwargs.update(kwargs)
        return (_Emission(), "s3://lake/curated/signals/x.parquet")

    monkeypatch.setenv("SEC_SIGNALS_RAW_BUCKET", "lake")
    monkeypatch.setenv("SEC_SIGNALS_AOSS_ENDPOINT", "https://abc.eu-west-1.aoss.amazonaws.com")
    monkeypatch.setattr(mod, "build_runtime", lambda settings=None, **kwargs: _Runtime())
    monkeypatch.setattr(mod, "emit_for_filing", fake_emit)
    monkeypatch.setattr(mod, "wait_until_accession_searchable", lambda **kwargs: True)

    code = mod.main(
        [
            "--bucket",
            "lake",
            "--cik",
            "0001403161",
            "--accession",
            "0001403161-25-000001",
            "--mode",
            "index_emit",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["mode"] == "index_emit"
    assert payload["warehouse_uri"] == "s3://lake/curated/signals/x.parquet"
    assert payload["indexed_chunks"] >= 1
    assert emit_kwargs["accession_number"] == "0001403161-25-000001"
    assert emit_kwargs["bucket"] == "lake"


def test_emit_only_skips_index(monkeypatch: Any, capsys: Any) -> None:
    from sec_signals.lake.raw import write_raw_filing

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

    class _Indexer:
        def upsert_chunks(self, chunks):  # noqa: ANN001
            raise AssertionError("emit_only must not index")

    class _Runtime:
        s3_client = s3
        bucket = "lake"
        indexer = _Indexer()
        retriever = object()
        extractor = object()
        aoss_client = object()

    class _Emission:
        ticker = type("T", (), {"value": "V"})()

    monkeypatch.setattr(mod, "build_runtime", lambda settings=None, **kwargs: _Runtime())
    monkeypatch.setattr(
        mod,
        "emit_for_filing",
        lambda **kwargs: (_Emission(), "s3://lake/curated/signals/x.parquet"),
    )

    code = mod.main(
        [
            "--bucket",
            "lake",
            "--cik",
            "0001403161",
            "--accession",
            "0001403161-25-000001",
            "--mode",
            "emit_only",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "emit_only"
    assert payload["indexed_chunks"] == 0
