"""Structured logging helpers (no secrets/PII)."""

from __future__ import annotations

import json
import logging
from typing import Any


_REDACT_KEYS = {"authorization", "api_key", "x-api-key", "password", "secret", "token"}


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def sanitize_extra(extra: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in extra.items():
        if key.lower() in _REDACT_KEYS or any(part in key.lower() for part in _REDACT_KEYS):
            clean[key] = "[REDACTED]"
        else:
            clean[key] = value
    return clean


def log_json(logger: logging.Logger, level: int, message: str, **fields: Any) -> None:
    payload = sanitize_extra(fields)
    logger.log(level, "%s %s", message, json.dumps(payload, default=str, sort_keys=True))
