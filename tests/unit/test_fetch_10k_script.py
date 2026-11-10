"""Local fetch_10k helper (mocked EdgarClient)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.fetch_10k import fetch_one, main


class _FakeEdgar:
    def latest_10k_for_ticker(self, ticker: str) -> dict[str, Any]:
        return {
            "ticker": ticker,
            "cik": "0001403161",
            "accession_number": "0001403161-25-000001",
            "form": "10-K",
            "filing_date": "2025-01-15",
            "primary_document": "v.htm",
        }

    def fetch_primary_document(self, filing: dict[str, Any]) -> bytes:
        return b"<html>demo</html>"


def test_fetch_one_writes_doc_and_meta(tmp_path: Path) -> None:
    meta = fetch_one(_FakeEdgar(), "V", tmp_path)  # type: ignore[arg-type]
    doc = Path(meta["local_path"])
    assert doc.read_bytes() == b"<html>demo</html>"
    sidecar = json.loads((doc.parent / "meta.json").read_text(encoding="utf-8"))
    assert sidecar["ticker"] == "V"
    assert sidecar["accession_number"] == "0001403161-25-000001"


def test_main_requires_user_agent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("SEC_EDGAR_USER_AGENT", raising=False)
    with pytest.raises(SystemExit) as exc:
        main(["--tickers", "V", "--out-dir", str(tmp_path)])
    assert exc.value.code != 0


def test_main_rejects_unknown_ticker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "Demo contact@example.com")
    code = main(["--tickers", "AAPL", "--out-dir", str(tmp_path)])
    assert code == 2
    assert "unknown ticker" in capsys.readouterr().err
