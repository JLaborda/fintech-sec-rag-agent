"""Locked Phase-1 enumerations."""

from enum import StrEnum


class DemoTicker(StrEnum):
    V = "V"
    MA = "MA"
    PYPL = "PYPL"
    XYZ = "XYZ"
    COIN = "COIN"


class FormType(StrEnum):
    TEN_K = "10-K"
    TEN_K_A = "10-K/A"


class FactorId(StrEnum):
    REGULATORY_AND_LEGAL_RISK = "regulatory_and_legal_risk"
    COMPETITIVE_POSITION = "competitive_position"
    MANAGEMENT_TONE = "management_tone"
    DEMAND_AND_GROWTH_OUTLOOK = "demand_and_growth_outlook"
    OPERATIONAL_AND_SUPPLY_RISK = "operational_and_supply_risk"


class FactorStatus(StrEnum):
    OK = "ok"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
