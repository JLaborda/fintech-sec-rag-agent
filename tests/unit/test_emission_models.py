"""Pydantic emission models (T006)."""

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from sec_signals.models.emission import (
    Citation,
    FactorSignal,
    KeyEvent,
    SignalEmission,
)
from sec_signals.models.enums import FactorId, FactorStatus, FormType


def _citation() -> Citation:
    return Citation(section="Risk Factors", item="Item 1A", quote="We face competition.")


def _ok_factor(factor_id: FactorId) -> FactorSignal:
    return FactorSignal(
        factor_id=factor_id,
        status=FactorStatus.OK,
        polarity=0.25,
        conviction=0.7,
        citation=_citation(),
        reasoning="Cited competition language supports mild positive polarity for this factor.",
    )


def _insufficient(factor_id: FactorId) -> FactorSignal:
    return FactorSignal(
        factor_id=factor_id,
        status=FactorStatus.INSUFFICIENT_EVIDENCE,
        reasoning="Searched Item 1A and Item 7; no usable evidence for this factor.",
    )


def _five_factors() -> list[FactorSignal]:
    ids = list(FactorId)
    return [_ok_factor(ids[0]), *[_insufficient(i) for i in ids[1:]]]


def test_ok_factor_requires_polarity_and_citation() -> None:
    factor = _ok_factor(FactorId.COMPETITIVE_POSITION)
    assert factor.polarity == 0.25
    assert factor.citation.quote


def test_insufficient_forbids_polarity() -> None:
    with pytest.raises(ValidationError):
        FactorSignal(
            factor_id=FactorId.MANAGEMENT_TONE,
            status=FactorStatus.INSUFFICIENT_EVIDENCE,
            polarity=0.1,
            reasoning="gap",
        )


def test_polarity_out_of_range_rejected() -> None:
    with pytest.raises(ValidationError):
        FactorSignal(
            factor_id=FactorId.MANAGEMENT_TONE,
            status=FactorStatus.OK,
            polarity=1.5,
            conviction=0.5,
            citation=_citation(),
            reasoning="bad",
        )


def test_emission_requires_schema_version_and_five_factors() -> None:
    emission = SignalEmission(
        factor_schema_version="0.1.0",
        model_or_pipeline_version="0.1.0",
        ticker="V",
        cik="0001403161",
        accession_number="0001403161-25-000001",
        form=FormType.TEN_K,
        filing_date=date(2025, 11, 15),
        factors=_five_factors(),
        disclaimer="Research / decision-support only — not investment advice.",
        emitted_at=datetime(2025, 11, 16, tzinfo=timezone.utc),
    )
    assert emission.factor_schema_version == "0.1.0"
    assert len(emission.factors) == 5


def test_emission_rejects_wrong_factor_count() -> None:
    with pytest.raises(ValidationError):
        SignalEmission(
            factor_schema_version="0.1.0",
            model_or_pipeline_version="0.1.0",
            ticker="V",
            cik="0001403161",
            accession_number="0001403161-25-000001",
            form=FormType.TEN_K,
            filing_date=date(2025, 11, 15),
            factors=_five_factors()[:4],
            disclaimer="Research / decision-support only — not investment advice.",
            emitted_at=datetime(2025, 11, 16, tzinfo=timezone.utc),
        )


def test_key_event_requires_citation() -> None:
    event = KeyEvent(summary="Acquired a competitor", citation=_citation())
    assert event.citation.item == "Item 1A"
