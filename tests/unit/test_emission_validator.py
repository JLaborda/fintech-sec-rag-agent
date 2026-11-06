"""Schema/provenance validator (T008)."""

from datetime import date, datetime, timezone

from sec_signals.models.enums import FactorId, FactorStatus
from sec_signals.validate.emission_validator import validate_and_drop_uncited


DISCLAIMER = "Research / decision-support only — not investment advice."


def _base_payload() -> dict:
    return {
        "factor_schema_version": "0.1.0",
        "model_or_pipeline_version": "0.1.0",
        "ticker": "PYPL",
        "cik": "0001633917",
        "accession_number": "0001633917-25-000001",
        "form": "10-K",
        "filing_date": "2025-02-10",
        "disclaimer": DISCLAIMER,
        "emitted_at": "2025-02-11T00:00:00Z",
        "factors": [
            {
                "factor_id": "regulatory_and_legal_risk",
                "status": "ok",
                "polarity": 0.1,
                "conviction": 0.5,
                "citation": {
                    "section": "Risk Factors",
                    "item": "Item 1A",
                    "quote": "We are subject to regulation.",
                },
                "reasoning": "Direct regulatory disclosure supports mild polarity.",
            },
            {
                "factor_id": "competitive_position",
                "status": "insufficient_evidence",
                "reasoning": "No competitive evidence located in retrieved chunks.",
            },
            {
                "factor_id": "management_tone",
                "status": "insufficient_evidence",
                "reasoning": "No tone evidence located in retrieved chunks.",
            },
            {
                "factor_id": "demand_and_growth_outlook",
                "status": "insufficient_evidence",
                "reasoning": "No demand evidence located in retrieved chunks.",
            },
            {
                "factor_id": "operational_and_supply_risk",
                "status": "insufficient_evidence",
                "reasoning": "No operational evidence located in retrieved chunks.",
            },
        ],
    }


def test_valid_payload_passes() -> None:
    emission = validate_and_drop_uncited(_base_payload())
    assert emission.ticker.value == "PYPL"
    assert emission.filing_date == date(2025, 2, 10)


def test_uncited_ok_becomes_insufficient_evidence() -> None:
    payload = _base_payload()
    payload["factors"][0] = {
        "factor_id": "regulatory_and_legal_risk",
        "status": "ok",
        "polarity": 0.2,
        "conviction": 0.6,
        "citation": {"section": "Risk Factors", "item": "Item 1A", "quote": ""},
        "reasoning": "Would have been ok but quote empty.",
    }
    emission = validate_and_drop_uncited(payload)
    factor = next(f for f in emission.factors if f.factor_id is FactorId.REGULATORY_AND_LEGAL_RISK)
    assert factor.status is FactorStatus.INSUFFICIENT_EVIDENCE
    assert factor.polarity is None
    assert "validation drop" in factor.reasoning.lower() or "dropped" in factor.reasoning.lower()


def test_missing_disclaimer_rejected() -> None:
    payload = _base_payload()
    del payload["disclaimer"]
    try:
        validate_and_drop_uncited(payload)
        raised = False
    except Exception:
        raised = True
    assert raised
