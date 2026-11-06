"""Batch emit for ticker list (shared by primary Fargate + secondary CLI/API)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from sec_signals.models.emission import SignalEmission
from sec_signals.models.enums import DemoTicker
from sec_signals.pipeline.emit import emit_for_filing


@dataclass
class FilingRef:
    ticker: DemoTicker
    cik: str
    accession_number: str
    form: str
    filing_date: str


@dataclass
class TickerEmitResult:
    ticker: DemoTicker
    status: str
    emission: SignalEmission | None = None
    warehouse_uri: str | None = None
    error_code: str | None = None
    error_message: str | None = None


ResolveLatest = Callable[[DemoTicker], FilingRef]


def batch_emit(
    tickers: list[str | DemoTicker],
    *,
    resolve_latest: ResolveLatest,
    retriever: Any,
    extractor: Any,
    s3_client: Any | None = None,
    bucket: str | None = None,
    persist_warehouse: bool = True,
    write_debug: bool = False,
) -> list[TickerEmitResult]:
    results: list[TickerEmitResult] = []
    for raw in tickers:
        ticker = raw if isinstance(raw, DemoTicker) else DemoTicker(raw)
        try:
            filing = resolve_latest(ticker)
            emission, warehouse_uri = emit_for_filing(
                retriever=retriever,
                extractor=extractor,
                ticker=filing.ticker,
                cik=filing.cik,
                accession_number=filing.accession_number,
                form=filing.form,
                filing_date=filing.filing_date,
                s3_client=s3_client,
                bucket=bucket,
                persist_warehouse=persist_warehouse,
                write_debug=write_debug,
            )
            results.append(
                TickerEmitResult(
                    ticker=ticker,
                    status="emitted",
                    emission=emission,
                    warehouse_uri=warehouse_uri,
                )
            )
        except Exception as exc:  # noqa: BLE001 — per-ticker isolation
            results.append(
                TickerEmitResult(
                    ticker=ticker,
                    status="error",
                    error_code="emit_failed",
                    error_message=str(exc),
                )
            )
    return results
