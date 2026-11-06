"""Demo ticker → CIK map."""

from __future__ import annotations

from sec_signals.models.enums import DemoTicker

# Zero-padded CIKs commonly used for these issuers (demo map; verify at ingest time).
TICKER_TO_CIK: dict[DemoTicker, str] = {
    DemoTicker.V: "0001403161",
    DemoTicker.MA: "0001141391",
    DemoTicker.PYPL: "0001633917",
    DemoTicker.XYZ: "0001512673",  # Block / Square
    DemoTicker.COIN: "0001679788",
}


def cik_for_ticker(ticker: DemoTicker | str) -> str:
    key = ticker if isinstance(ticker, DemoTicker) else DemoTicker(ticker)
    return TICKER_TO_CIK[key]
