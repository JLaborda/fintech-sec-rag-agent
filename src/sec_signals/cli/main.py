"""sec-signals CLI entrypoint."""

from __future__ import annotations

import typer

from sec_signals.cli import emit_cmd, index_cmd, ingest_cmd

app = typer.Typer(
    name="sec-signals",
    help=(
        "Phase-1 SEC 10-K qualitative signals. "
        "Primary path is on-ingest S3→Fargate; CLI emit is re-emit/backfill only."
    ),
    no_args_is_help=True,
)

emit_cmd.register(app)
ingest_cmd.register(app)
index_cmd.register(app)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
