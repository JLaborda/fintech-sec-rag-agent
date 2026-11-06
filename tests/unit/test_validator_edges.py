"""Validator edge cases (T049)."""

import pytest

from sec_signals.validate.emission_validator import validate_and_drop_uncited


def _payload(**overrides):
    base = {
        "factor_schema_version": "0.1.0",
        "model_or_pipeline_version": "0.1.0",
        "ticker": "V",
        "cik": "0001403161",
        "accession_number": "0001403161-25-000001",
        "form": "10-K/A",
        "filing_date": "2025-11-15",
        "disclaimer": "Research / decision-support only — not investment advice.",
        "emitted_at": "2025-11-16T12:00:00Z",
        "factors": [
            {
                "factor_id": "regulatory_and_legal_risk",
                "status": "insufficient_evidence",
                "reasoning": "gap",
            },
            {
                "factor_id": "competitive_position",
                "status": "insufficient_evidence",
                "reasoning": "gap",
            },
            {
                "factor_id": "management_tone",
                "status": "insufficient_evidence",
                "reasoning": "gap",
            },
            {
                "factor_id": "demand_and_growth_outlook",
                "status": "insufficient_evidence",
                "reasoning": "gap",
            },
            {
                "factor_id": "operational_and_supply_risk",
                "status": "insufficient_evidence",
                "reasoning": "gap",
            },
        ],
    }
    base.update(overrides)
    return base


def test_accepts_10k_amendment_form() -> None:
    emission = validate_and_drop_uncited(_payload())
    assert emission.form.value == "10-K/A"


def test_missing_filing_date_rejected() -> None:
    payload = _payload()
    del payload["filing_date"]
    with pytest.raises(Exception):
        validate_and_drop_uncited(payload)


def test_out_of_range_polarity_dropped_or_rejected() -> None:
    payload = _payload()
    payload["factors"][0] = {
        "factor_id": "regulatory_and_legal_risk",
        "status": "ok",
        "polarity": 5.0,
        "conviction": 0.5,
        "citation": {
            "section": "Risk Factors",
            "item": "Item 1A",
            "quote": "regulation",
        },
        "reasoning": "bad polarity",
    }
    with pytest.raises(Exception):
        validate_and_drop_uncited(payload)
