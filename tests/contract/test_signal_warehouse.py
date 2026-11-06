"""Contract tests for warehouse row shape / partitions (T057)."""

from __future__ import annotations

import json
from pathlib import Path

from sec_signals.models.emission import SignalEmission
from sec_signals.models.warehouse import flatten_emission
from sec_signals.warehouse.parquet_writer import build_curated_key, rows_to_table

ROOT = Path(__file__).resolve().parents[2]


def test_flatten_valid_fixture_has_hive_partitions() -> None:
    payload = json.loads((ROOT / "fixtures/emissions/valid_ok_mix.json").read_text())
    emission = SignalEmission.model_validate(payload)
    rows = flatten_emission(emission)
    assert len(rows) == 5
    assert all(r.ticker.value == "V" for r in rows)
    assert all(r.filing_date.isoformat() == "2025-11-15" for r in rows)
    key = build_curated_key(
        ticker="V",
        filing_date="2025-11-15",
        accession_number="0001403161-25-000001",
        pipeline_version="0.1.0",
    )
    assert "factor_schema_version=0.1.0" in key
    assert "ticker=V" in key
    assert "filing_date=2025-11-15" in key
    table = rows_to_table(rows)
    assert table.num_rows == 5
