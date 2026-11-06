"""Haiku 4.5 factor extraction."""

from __future__ import annotations

import json
import re
from typing import Any

from sec_signals.extract.bedrock_converse import BedrockConverseClient
from sec_signals.models.enums import FactorId
from sec_signals.models.filing import Chunk

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)

SYSTEM_PROMPT = (
    "You extract hermetic qualitative factors from SEC 10-K excerpts. "
    "Return JSON only for factor schema 0.1.0. "
    "Never invent polarity without a verbatim citation quote from the excerpts. "
    "Use insufficient_evidence when evidence is missing. "
    "Outputs are research/decision-support signals, not investment advice."
)


def parse_factors_payload(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    match = _FENCE_RE.search(cleaned)
    if match:
        cleaned = match.group(1).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError("model output is not valid JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("model output must be a JSON object")
    data.setdefault("factors", [])
    data.setdefault("key_events", [])
    return data


def _pack_chunks(chunks_by_factor: dict[FactorId, list[Chunk]]) -> str:
    parts: list[str] = []
    for factor_id, chunks in chunks_by_factor.items():
        parts.append(f"## factor={factor_id.value}")
        for chunk in chunks:
            parts.append(
                f"[{chunk.item} | {chunk.section} | chunk_id={chunk.chunk_id}]\n{chunk.text}"
            )
    return "\n\n".join(parts)


class FactorExtractor:
    def __init__(self, client: BedrockConverseClient | None = None) -> None:
        self._client = client or BedrockConverseClient()

    def extract(self, chunks_by_factor: dict[FactorId, list[Chunk]]) -> dict[str, Any]:
        user = (
            "Closed factor catalog: "
            + ", ".join(f.value for f in FactorId)
            + "\n\nExcerpts:\n"
            + _pack_chunks(chunks_by_factor)
            + "\n\nReturn JSON with keys factors (array of 5) and optional key_events."
        )
        raw = self._client.converse_text(SYSTEM_PROMPT, user)
        return parse_factors_payload(raw)
