"""JSON Schema + provenance validator for SignalEmission."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator

from sec_signals.models.emission import SignalEmission
from sec_signals.models.enums import FactorId, FactorStatus

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "specs"
    / "001-10k-signal-demo"
    / "contracts"
    / "signal-emission.schema.json"
)


def load_emission_schema() -> dict[str, Any]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _drop_uncited_ok_factors(payload: dict[str, Any]) -> dict[str, Any]:
    factors = payload.get("factors")
    if not isinstance(factors, list):
        return payload
    cleaned: list[dict[str, Any]] = []
    for factor in factors:
        if not isinstance(factor, dict):
            cleaned.append(factor)
            continue
        if factor.get("status") != "ok":
            cleaned.append(factor)
            continue
        citation = factor.get("citation") or {}
        quote = citation.get("quote") if isinstance(citation, dict) else None
        section = citation.get("section") if isinstance(citation, dict) else None
        item = citation.get("item") if isinstance(citation, dict) else None
        if quote and section and item:
            cleaned.append(factor)
            continue
        factor_id = factor.get("factor_id", "unknown")
        cleaned.append(
            {
                "factor_id": factor_id,
                "status": FactorStatus.INSUFFICIENT_EVIDENCE.value,
                "reasoning": (
                    f"Scored claim for {factor_id} dropped by validation drop: "
                    "missing required citation/provenance for an ok factor."
                ),
            }
        )
    out = dict(payload)
    out["factors"] = cleaned
    return out


def validate_and_drop_uncited(payload: dict[str, Any]) -> SignalEmission:
    """Validate payload; drop uncited ok claims to insufficient_evidence."""
    if "disclaimer" not in payload or not str(payload.get("disclaimer") or "").strip():
        raise ValueError("disclaimer is required (research-not-advice framing)")

    normalized = _drop_uncited_ok_factors(payload)
    schema = load_emission_schema()
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(normalized), key=lambda e: e.path)
    if errors:
        messages = "; ".join(error.message for error in errors[:5])
        raise jsonschema.ValidationError(messages)

    # Ensure closed catalog coverage after drops
    ids = {f.get("factor_id") for f in normalized["factors"]}
    if ids != {f.value for f in FactorId}:
        raise ValueError("factors must cover closed catalog after validation")

    return SignalEmission.model_validate(normalized)
