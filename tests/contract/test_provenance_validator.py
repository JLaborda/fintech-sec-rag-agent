"""Contract tests for provenance / uncited drop (T014)."""

from __future__ import annotations

import json
from pathlib import Path

from sec_signals.models.enums import FactorId, FactorStatus
from sec_signals.validate.emission_validator import validate_and_drop_uncited

ROOT = Path(__file__).resolve().parents[2]


def test_uncited_ok_fixture_is_dropped() -> None:
    payload = json.loads((ROOT / "fixtures/emissions/uncited_ok_to_drop.json").read_text())
    emission = validate_and_drop_uncited(payload)
    factor = next(f for f in emission.factors if f.factor_id is FactorId.REGULATORY_AND_LEGAL_RISK)
    assert factor.status is FactorStatus.INSUFFICIENT_EVIDENCE
    assert factor.polarity is None


def test_valid_mix_fixture_keeps_ok_factors() -> None:
    payload = json.loads((ROOT / "fixtures/emissions/valid_ok_mix.json").read_text())
    emission = validate_and_drop_uncited(payload)
    ok_ids = {f.factor_id for f in emission.factors if f.status is FactorStatus.OK}
    assert FactorId.REGULATORY_AND_LEGAL_RISK in ok_ids
    assert FactorId.COMPETITIVE_POSITION in ok_ids
