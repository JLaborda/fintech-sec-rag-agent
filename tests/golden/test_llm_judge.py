"""LLM-as-judge golden runner (T039–T040) — gated by CI path filters."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.llm_judge
def test_golden_fixture_loads_and_skips_without_bedrock() -> None:
    case_path = ROOT / "fixtures/golden/regulatory_v.json"
    case = json.loads(case_path.read_text())
    assert case["factor_id"] == "regulatory_and_legal_risk"
    if os.getenv("RUN_LLM_JUDGE") != "1" or not os.getenv("AWS_ACCESS_KEY_ID"):
        pytest.skip("LLM judge requires RUN_LLM_JUDGE=1 and AWS credentials")
    # Live judge path would call Bedrock Haiku 4.5 with the same EU geo profile.
    assert case["expected_status"] in {"ok", "insufficient_evidence"}
