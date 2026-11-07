"""Fail-closed API auth for Lambda / demo (T037)."""

from __future__ import annotations

import pytest

from sec_signals.api.auth import UnauthorizedError, authorize_request, require_api_key


def test_require_api_key_allows_missing_key_outside_lambda(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEMO_API_KEY", raising=False)
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    monkeypatch.delenv("DEMO_REQUIRE_API_KEY", raising=False)
    require_api_key({})  # local / unit tests: auth optional


def test_require_api_key_fails_closed_in_lambda_without_configured_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEMO_API_KEY", raising=False)
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "demo-emit")
    with pytest.raises(UnauthorizedError, match="not configured"):
        require_api_key({})


def test_require_api_key_fails_closed_when_demo_flag_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEMO_API_KEY", raising=False)
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    monkeypatch.setenv("DEMO_REQUIRE_API_KEY", "true")
    with pytest.raises(UnauthorizedError, match="not configured"):
        require_api_key({})


def test_require_api_key_rejects_wrong_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_API_KEY", "secret")
    with pytest.raises(UnauthorizedError, match="invalid"):
        require_api_key({"x-api-key": "wrong"})


def test_require_api_key_accepts_matching_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_API_KEY", "secret")
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "demo-emit")
    require_api_key({"X-Api-Key": "secret"})


def test_authorize_request_reads_event_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_API_KEY", "secret")
    authorize_request({"headers": {"x-api-key": "secret"}})
    with pytest.raises(UnauthorizedError):
        authorize_request({"headers": {}})
