"""API auth hooks for internal demo (API key and/or SigV4)."""

from __future__ import annotations

import os
from typing import Any


class UnauthorizedError(Exception):
    pass


def require_api_key(headers: dict[str, str], *, expected: str | None = None) -> None:
    expected_key = expected if expected is not None else os.getenv("DEMO_API_KEY", "")
    if not expected_key:
        # Auth disabled when no key configured (local tests).
        return
    provided = headers.get("x-api-key") or headers.get("X-Api-Key") or ""
    if provided != expected_key:
        raise UnauthorizedError("invalid or missing API key")


def authorize_request(event: dict[str, Any]) -> None:
    headers = {str(k): str(v) for k, v in (event.get("headers") or {}).items()}
    # Prefer API key when configured; IAM/SigV4 enforced at API Gateway when enabled.
    require_api_key(headers)
