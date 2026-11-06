"""Foundational enum contract (T005)."""

from sec_signals.models.enums import DemoTicker, FactorId, FactorStatus, FormType


def test_demo_tickers_are_locked_universe() -> None:
    assert {t.value for t in DemoTicker} == {"V", "MA", "PYPL", "XYZ", "COIN"}


def test_form_types_are_10k_only() -> None:
    assert {f.value for f in FormType} == {"10-K", "10-K/A"}


def test_factor_catalog_has_exactly_five_locked_ids() -> None:
    assert [f.value for f in FactorId] == [
        "regulatory_and_legal_risk",
        "competitive_position",
        "management_tone",
        "demand_and_growth_outlook",
        "operational_and_supply_risk",
    ]


def test_factor_status_values() -> None:
    assert {s.value for s in FactorStatus} == {"ok", "insufficient_evidence"}
