"""T002 foundation: indexing Settings knobs (CA-1 / embed + bulk)."""

from __future__ import annotations

import pytest

from sec_signals.config import Settings


def test_embed_concurrency_default_eight_and_opensearch_bulk_size_default_fifty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SEC_SIGNALS_EMBED_CONCURRENCY", raising=False)
    monkeypatch.delenv("SEC_SIGNALS_OPENSEARCH_BULK_SIZE", raising=False)
    settings = Settings.from_env()
    assert settings.embed_concurrency == 8
    assert settings.opensearch_bulk_size == 50


def test_embed_concurrency_and_opensearch_bulk_size_read_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEC_SIGNALS_EMBED_CONCURRENCY", "4")
    monkeypatch.setenv("SEC_SIGNALS_OPENSEARCH_BULK_SIZE", "3")
    settings = Settings.from_env()
    assert settings.embed_concurrency == 4
    assert settings.opensearch_bulk_size == 3
