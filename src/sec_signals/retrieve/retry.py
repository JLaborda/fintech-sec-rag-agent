"""Shared exponential backoff helper for Bedrock / OpenSearch calls (CA-3)."""

from __future__ import annotations

import random
import time
from collections.abc import Callable

DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_BASE_DELAY_SECONDS = 0.5


def call_with_backoff[T](
    fn: Callable[[], T],
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    base_delay: float = DEFAULT_BASE_DELAY_SECONDS,
    is_retriable: Callable[[BaseException], bool] | None = None,
) -> T:
    """Call ``fn`` until it succeeds or ``max_attempts`` is exhausted.

    On retriable failures, sleeps with full jitter in ``[0, delay]`` where
    ``delay = base_delay * (2 ** (attempt - 1))`` before the next attempt.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            retriable = is_retriable(exc) if is_retriable is not None else True
            if not retriable or attempt >= max_attempts:
                raise
            delay = base_delay * (2 ** (attempt - 1))
            time.sleep(random.uniform(0, delay))

    assert last_exc is not None  # pragma: no cover
    raise last_exc
