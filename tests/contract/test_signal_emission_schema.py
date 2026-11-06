"""Contract tests for hermetic schema (T013)."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads(
    (ROOT / "specs/001-10k-signal-demo/contracts/signal-emission.schema.json").read_text()
)
FIXTURE = json.loads((ROOT / "fixtures/emissions/valid_ok_mix.json").read_text())
CATALOG = {
    "regulatory_and_legal_risk",
    "competitive_position",
    "management_tone",
    "demand_and_growth_outlook",
    "operational_and_supply_risk",
}


def test_valid_fixture_matches_schema() -> None:
    Draft202012Validator(SCHEMA).validate(FIXTURE)


def test_fixture_has_exactly_five_catalog_factors() -> None:
    ids = [f["factor_id"] for f in FIXTURE["factors"]]
    assert len(ids) == 5
    assert set(ids) == CATALOG


def test_ok_polarity_and_conviction_ranges() -> None:
    for factor in FIXTURE["factors"]:
        if factor["status"] != "ok":
            continue
        assert -1.0 <= factor["polarity"] <= 1.0
        assert 0.0 <= factor["conviction"] <= 1.0
        assert factor["citation"]["quote"]


def test_rejects_unknown_factor_id() -> None:
    bad = json.loads(json.dumps(FIXTURE))
    bad["factors"][2]["factor_id"] = "made_up_factor"
    with pytest.raises(jsonschema.ValidationError):
        Draft202012Validator(SCHEMA).validate(bad)
