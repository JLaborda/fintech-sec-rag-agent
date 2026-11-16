"""T001 foundation: call_with_backoff retries with exponential backoff (CA-3 / FR-003)."""

from __future__ import annotations

import pytest

from sec_signals.retrieve.retry import call_with_backoff


class RetriableError(Exception):
    """Test stand-in for throttling / transient failures."""


def _is_retriable(exc: BaseException) -> bool:
    return isinstance(exc, RetriableError)


def test_call_with_backoff_retries_retriable_error_with_exponential_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = {"n": 0}
    sleeps: list[float] = []

    def flaky() -> str:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RetriableError("throttle")
        return "ok"

    monkeypatch.setattr("sec_signals.retrieve.retry.time.sleep", sleeps.append)
    # Full jitter in [0, delay]; pin to upper bound to assert exact exponential delays.
    monkeypatch.setattr("sec_signals.retrieve.retry.random.uniform", lambda _a, b: b)

    result = call_with_backoff(flaky, is_retriable=_is_retriable)

    assert result == "ok"
    assert attempts["n"] == 3
    # base_delay=0.5 → 0.5 * 2**(attempt-1) after attempts 1 and 2
    assert sleeps == [0.5, 1.0]


def test_call_with_backoff_respects_max_attempts_five(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = {"n": 0}
    sleeps: list[float] = []

    def always_fail() -> None:
        attempts["n"] += 1
        raise RetriableError("always")

    monkeypatch.setattr("sec_signals.retrieve.retry.time.sleep", sleeps.append)
    monkeypatch.setattr("sec_signals.retrieve.retry.random.uniform", lambda _a, b: b)

    with pytest.raises(RetriableError):
        call_with_backoff(always_fail, is_retriable=_is_retriable)

    assert attempts["n"] == 5
    assert sleeps == [0.5, 1.0, 2.0, 4.0]
