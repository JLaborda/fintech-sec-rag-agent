"""CLI ingest/emit exit paths with injected runtime (no live AWS)."""

from __future__ import annotations

from typing import Any

from typer.testing import CliRunner

from sec_signals.cli.main import app

runner = CliRunner()


def test_cli_ingest_success(monkeypatch: Any) -> None:
    monkeypatch.setenv("SEC_SIGNALS_RAW_BUCKET", "lake")
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "DemoAgent contact@example.com")

    def fake_ingest(tickers, **kwargs):  # noqa: ANN003
        return [{"ticker": "V", "uri": "s3://lake/raw/edgar/x/y/z.htm", "accession_number": "a"}]

    monkeypatch.setattr("sec_signals.cli.ingest_cmd.ingest_tickers", fake_ingest)
    monkeypatch.setattr(
        "sec_signals.cli.ingest_cmd.build_edgar_and_s3",
        lambda settings: (object(), object(), settings.raw_bucket),
    )
    result = runner.invoke(app, ["ingest", "--tickers", "V"])
    assert result.exit_code == 0
    assert "s3://lake/raw/edgar" in result.stdout


def test_cli_ingest_requires_user_agent(monkeypatch: Any) -> None:
    monkeypatch.delenv("SEC_EDGAR_USER_AGENT", raising=False)
    monkeypatch.setenv("SEC_SIGNALS_RAW_BUCKET", "lake")
    result = runner.invoke(app, ["ingest", "--tickers", "V"])
    assert result.exit_code == 4
    assert "SEC_EDGAR_USER_AGENT" in result.stdout


def test_cli_emit_success(monkeypatch: Any) -> None:
    monkeypatch.setenv("SEC_SIGNALS_RAW_BUCKET", "lake")
    monkeypatch.setenv("SEC_SIGNALS_AOSS_ENDPOINT", "https://abc.eu-west-1.aoss.amazonaws.com")

    class _Emission:
        ticker = type("T", (), {"value": "V"})()
        accession_number = "0001403161-25-000001"

    class _Result:
        ticker = type("T", (), {"value": "V"})()
        status = "emitted"
        emission = _Emission()
        warehouse_uri = "s3://lake/curated/signals/x.parquet"
        error_message = None

    monkeypatch.setattr("sec_signals.cli.emit_cmd.build_runtime", lambda: object())
    monkeypatch.setattr(
        "sec_signals.cli.emit_cmd.run_cli_emit",
        lambda **kwargs: [_Result()],
    )
    result = runner.invoke(app, ["emit", "--tickers", "V", "--no-persist-warehouse"])
    assert result.exit_code == 0
    assert "emitted" in result.stdout.lower() or "V" in result.stdout
