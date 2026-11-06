"""Secondary CLI re-emit / backfill against live AOSS + warehouse."""

from __future__ import annotations

from typing import Any

from sec_signals.aws.runtime import RuntimeClients
from sec_signals.edgar.universe import cik_for_ticker
from sec_signals.lake.raw import load_provenance, raw_object_prefix
from sec_signals.models.enums import DemoTicker
from sec_signals.pipeline.batch_emit import FilingRef, TickerEmitResult, batch_emit


def _list_accessions(s3_client: Any, bucket: str, cik: str) -> list[str]:
    prefix = f"raw/edgar/{cik}/"
    paginator = getattr(s3_client, "get_paginator", None)
    accessions: set[str] = set()
    if callable(paginator):
        pages = s3_client.get_paginator("list_objects_v2").paginate(
            Bucket=bucket, Prefix=prefix
        )
        for page in pages:
            for obj in page.get("Contents") or []:
                key = obj["Key"]
                parts = key.split("/")
                if len(parts) >= 4:
                    accessions.add(parts[3])
    else:
        # Minimal fake / test clients may only expose list_objects_v2.
        response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        for obj in response.get("Contents") or []:
            parts = obj["Key"].split("/")
            if len(parts) >= 4:
                accessions.add(parts[3])
    return sorted(accessions)


def resolve_latest_from_lake(runtime: RuntimeClients, ticker: DemoTicker) -> FilingRef:
    cik = cik_for_ticker(ticker)
    accessions = _list_accessions(runtime.s3_client, runtime.bucket, cik)
    if not accessions:
        raise FileNotFoundError(f"no raw filings in lake for {ticker.value} cik={cik}")
    # Prefer lexicographically latest accession; refine via provenance filing_date.
    best: FilingRef | None = None
    for accession in accessions:
        try:
            prov = load_provenance(runtime.s3_client, runtime.bucket, cik, accession)
        except Exception:  # noqa: BLE001
            continue
        candidate = FilingRef(
            ticker=ticker,
            cik=prov["cik"],
            accession_number=prov["accession_number"],
            form=prov["form"],
            filing_date=prov["filing_date"],
        )
        if best is None or (candidate.filing_date, candidate.accession_number) > (
            best.filing_date,
            best.accession_number,
        ):
            best = candidate
    if best is None:
        prefix = raw_object_prefix(cik, "*")
        raise FileNotFoundError(
            f"no readable provenance for {ticker.value} under {prefix}"
        )
    return best


def run_cli_emit(
    *,
    tickers: list[str],
    runtime: RuntimeClients,
    persist_warehouse: bool = True,
    accession: str | None = None,
    write_debug: bool = False,
) -> list[TickerEmitResult]:
    def resolve(ticker: DemoTicker) -> FilingRef:
        if accession:
            cik = cik_for_ticker(ticker)
            prov = load_provenance(runtime.s3_client, runtime.bucket, cik, accession)
            return FilingRef(
                ticker=ticker,
                cik=prov["cik"],
                accession_number=prov["accession_number"],
                form=prov["form"],
                filing_date=prov["filing_date"],
            )
        return resolve_latest_from_lake(runtime, ticker)

    return batch_emit(
        tickers,
        resolve_latest=resolve,
        retriever=runtime.retriever,
        extractor=runtime.extractor,
        s3_client=runtime.s3_client if persist_warehouse or write_debug else None,
        bucket=runtime.bucket if persist_warehouse or write_debug else None,
        persist_warehouse=persist_warehouse,
        write_debug=write_debug,
    )
