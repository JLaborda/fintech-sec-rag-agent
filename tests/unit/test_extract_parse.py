"""Unit tests for extract JSON parse helpers (T015)."""

import pytest

from sec_signals.extract.factor_extractor import parse_factors_payload


def test_parse_factors_payload_accepts_json_object() -> None:
    text = '{"factors": [], "key_events": []}'
    parsed = parse_factors_payload(text)
    assert parsed["factors"] == []


def test_parse_factors_payload_strips_fences() -> None:
    text = """```json
{"factors": [{"factor_id": "management_tone"}], "key_events": []}
```"""
    parsed = parse_factors_payload(text)
    assert parsed["factors"][0]["factor_id"] == "management_tone"


def test_parse_factors_payload_rejects_non_json() -> None:
    with pytest.raises(ValueError):
        parse_factors_payload("not-json")
