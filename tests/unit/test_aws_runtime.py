"""Live AWS runtime factory (mocked boto3 / AOSS)."""

from __future__ import annotations

from typing import Any

import pytest

from sec_signals.aws.runtime import RuntimeClients, build_runtime, require_settings_for_live
from sec_signals.config import Settings


class _FakeS3:
    pass


class _FakeBedrock:
    pass


class _FakeAoss:
    def __init__(self) -> None:
        self.index_name = "sec-10k-chunks"

    def index(self, **kwargs):  # noqa: ANN003
        return {"result": "created"}

    def search(self, **kwargs):  # noqa: ANN003
        return {"hits": {"hits": []}}

    def delete_by_query(self, **kwargs):  # noqa: ANN003
        return {"deleted": 0}


def test_require_settings_for_live_raises_when_bucket_missing() -> None:
    settings = Settings(raw_bucket="", aoss_endpoint="https://example.aoss.amazonaws.com")
    with pytest.raises(ValueError, match="SEC_SIGNALS_RAW_BUCKET"):
        require_settings_for_live(settings)


def test_require_settings_for_live_raises_when_aoss_missing() -> None:
    settings = Settings(raw_bucket="lake", aoss_endpoint="")
    with pytest.raises(ValueError, match="SEC_SIGNALS_AOSS_ENDPOINT"):
        require_settings_for_live(settings)


def test_build_runtime_wires_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        raw_bucket="demo-lake",
        aoss_endpoint="https://abc.eu-west-1.aoss.amazonaws.com",
        edgar_user_agent="DemoAgent contact@example.com",
    )

    def fake_s3_client(*, region_name: str) -> Any:
        assert region_name == "eu-west-1"
        return _FakeS3()

    def fake_bedrock_client(*, region_name: str) -> Any:
        return _FakeBedrock()

    def fake_aoss(*, endpoint: str, region: str, index_name: str = "sec-10k-chunks", **kwargs: Any) -> Any:
        assert endpoint.startswith("https://")
        assert region == "eu-west-1"
        assert kwargs.get("ensure_knn_index") is True
        return _FakeAoss()

    monkeypatch.setattr("sec_signals.aws.runtime.boto3.client", lambda service, **kw: {
        "s3": fake_s3_client,
        "bedrock-runtime": fake_bedrock_client,
    }[service](**kw))
    monkeypatch.setattr("sec_signals.aws.runtime.build_aoss_client", fake_aoss)

    runtime = build_runtime(settings)
    assert isinstance(runtime, RuntimeClients)
    assert runtime.bucket == "demo-lake"
    assert runtime.s3_client is not None
    assert runtime.indexer is not None
    assert runtime.retriever is not None
    assert runtime.extractor is not None

    overridden = build_runtime(settings, raw_bucket="override-lake")
    assert overridden.bucket == "override-lake"
