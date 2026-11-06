"""CLI emit/validate golden path (T033)."""

from typer.testing import CliRunner

from sec_signals.cli.main import app

runner = CliRunner()


def test_cli_help_marks_emit_as_secondary() -> None:
    result = runner.invoke(app, ["emit", "--help"])
    assert result.exit_code == 0
    assert "re-emit" in result.stdout.lower() or "backfill" in result.stdout.lower()


def test_cli_validate_fixture() -> None:
    result = runner.invoke(
        app,
        ["validate", "--file", "fixtures/emissions/valid_ok_mix.json"],
    )
    assert result.exit_code == 0
    assert "valid" in result.stdout.lower()
