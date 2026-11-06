"""Config + Bedrock client wrappers (T009–T011)."""

import json
from io import BytesIO

import pytest

from sec_signals.config import Settings
from sec_signals.extract.bedrock_converse import BedrockConverseClient
from sec_signals.retrieve.titan_embed import TitanEmbedClient


def test_settings_defaults_lock_haiku_and_titan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SEC_SIGNALS_LLM_MODEL_ID", raising=False)
    monkeypatch.delenv("SEC_SIGNALS_EMBED_MODEL_ID", raising=False)
    settings = Settings.from_env()
    assert settings.aws_region == "eu-west-1"
    assert settings.llm_model_id == "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert settings.embed_model_id == "amazon.titan-embed-text-v2:0"
    assert settings.embed_dimensions == 1024


class _FakeConverse:
    def converse(self, **kwargs):  # noqa: ANN003
        assert kwargs["modelId"] == "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
        return {"output": {"message": {"content": [{"text": '{"ok": true}'}]}}}


class _FakeEmbed:
    def invoke_model(self, **kwargs):  # noqa: ANN003
        assert kwargs["modelId"] == "amazon.titan-embed-text-v2:0"
        body = json.dumps({"embedding": [0.0] * 1024}).encode("utf-8")
        return {"body": BytesIO(body)}


def test_converse_uses_haiku_profile() -> None:
    client = BedrockConverseClient(client=_FakeConverse())
    assert client.converse_text("sys", "user") == '{"ok": true}'


def test_titan_embed_returns_1024() -> None:
    client = TitanEmbedClient(client=_FakeEmbed())
    vector = client.embed("hello")
    assert len(vector) == 1024


def test_rejects_non_haiku_model() -> None:
    with pytest.raises(ValueError):
        BedrockConverseClient(model_id="eu.anthropic.claude-sonnet-4-5-20250929-v1:0", client=_FakeConverse())
