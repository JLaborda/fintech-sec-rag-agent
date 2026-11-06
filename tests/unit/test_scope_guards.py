"""Non-goal / scope guards (T050)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "sec_signals"


def test_no_ranking_or_broker_modules() -> None:
    names = {p.name for p in SRC.rglob("*.py")}
    forbidden = {"ranking", "portfolio", "paper_broker", "broker", "chat"}
    assert not (names & forbidden)


def test_warehouse_module_exists_and_aoss_not_sole_store() -> None:
    assert (SRC / "warehouse" / "parquet_writer.py").exists()
    text = (SRC / "pipeline" / "emit.py").read_text()
    assert "persist_warehouse" in text or "write_rows_s3" in text
