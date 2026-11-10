#!/usr/bin/env python3
"""Descarga local del último 10-K/10-K/A (demo sin S3).

Production / lake path (dispara el pipeline primario):

  export SEC_EDGAR_USER_AGENT="YourOrg contact@example.com"
  export SEC_SIGNALS_RAW_BUCKET="<bucket>"
  uv run sec-signals ingest --tickers V

Este script solo escribe el HTML/primary document en disco para demos e
entrevistas. Reutiliza ``EdgarClient`` + mapa ticker→CIK del paquete.

Patrones tomados de SmartWealthAI ``investing.sec_client``:
  - User-Agent identificable vía env (aquí ``SEC_EDGAR_USER_AGENT``)
  - throttle cortés entre requests SEC (~8 req/s en el client)

Ejemplo:

  export SEC_EDGAR_USER_AGENT="YourOrg contact@example.com"
  uv run python scripts/fetch_10k.py --tickers V
  uv run python scripts/fetch_10k.py --tickers V,MA --out-dir /tmp/10k-demo
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from sec_signals.edgar.client import EdgarClient
from sec_signals.models.enums import DemoTicker


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch latest 10-K/10-K/A primary docs locally (no S3)."
    )
    parser.add_argument(
        "--tickers",
        required=True,
        help="Comma-separated demo tickers (V,MA,PYPL,XYZ,COIN).",
    )
    parser.add_argument(
        "--out-dir",
        default="data/local/edgar",
        help="Directory for downloaded filings (default: data/local/edgar).",
    )
    return parser.parse_args(argv)


def _require_user_agent() -> str:
    user_agent = os.environ.get("SEC_EDGAR_USER_AGENT", "").strip()
    if not user_agent:
        raise SystemExit(
            "SEC_EDGAR_USER_AGENT is required "
            '(example: export SEC_EDGAR_USER_AGENT="YourOrg contact@example.com")'
        )
    return user_agent


def fetch_one(edgar: EdgarClient, ticker: str, out_dir: Path) -> dict[str, str]:
    filing = edgar.latest_10k_for_ticker(ticker)
    raw = edgar.fetch_primary_document(filing)
    cik = str(filing["cik"])
    accession = str(filing["accession_number"])
    primary = str(filing["primary_document"])
    dest = out_dir / cik / accession
    dest.mkdir(parents=True, exist_ok=True)
    doc_path = dest / primary
    meta_path = dest / "meta.json"
    doc_path.write_bytes(raw)
    meta = {
        "ticker": filing["ticker"],
        "cik": cik,
        "accession_number": accession,
        "form": filing["form"],
        "filing_date": filing["filing_date"],
        "primary_document": primary,
        "local_path": str(doc_path),
        "source_url": (
            "https://www.sec.gov/Archives/edgar/data/"
            f"{cik.lstrip('0') or '0'}/{accession.replace('-', '')}/{primary}"
        ),
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    user_agent = _require_user_agent()
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    if not tickers:
        print("at least one ticker is required", file=sys.stderr)
        return 2

    allowed = {t.value for t in DemoTicker}
    unknown = [t for t in tickers if t not in allowed]
    if unknown:
        print(
            f"unknown ticker(s): {', '.join(unknown)}; "
            f"demo universe is {', '.join(sorted(allowed))}",
            file=sys.stderr,
        )
        return 2

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    edgar = EdgarClient(user_agent=user_agent)

    any_error = False
    for ticker in tickers:
        try:
            meta = fetch_one(edgar, ticker, out_dir)
            print(
                f"ok {meta['ticker']} form={meta['form']} "
                f"accession={meta['accession_number']} path={meta['local_path']}"
            )
        except Exception as exc:  # noqa: BLE001 — per-ticker isolation for demos
            any_error = True
            print(f"error {ticker}: {exc}", file=sys.stderr)

    if any_error:
        return 1
    print(
        "Tip: para el lake S3 + pipeline primario usa "
        "`uv run sec-signals ingest --tickers …` "
        "(requiere SEC_SIGNALS_RAW_BUCKET)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
