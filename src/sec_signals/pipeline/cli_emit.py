"""Secondary CLI re-emit / backfill against live AOSS + warehouse."""

from __future__ import annotations

from typing import Any

from sec_signals.aws.runtime import RuntimeClients
from sec_signals.edgar.universe import cik_for_ticker
from sec_signals.lake.raw import load_provenance, raw_object_prefix
from sec_signals.models.enums import DemoTicker
from sec_signals.pipeline.batch_emit import FilingRef, TickerEmitResult, batch_emit


def _is_missing_object(exc: BaseException) -> bool:
    name = type(exc).__name__
    msg = str(exc).lower()
    return name in {"NoSuchKey", "ClientError"} or "nosuchkey" in msg or "not found" in msg


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


def _accession_indexed(runtime: RuntimeClients, accession_number: str) -> bool:
    """Return True when AOSS has at least one chunk for the accession."""
    client = runtime.aoss_client
    try:
        result = client.search(
            index=getattr(client, "index_name", "sec-10k-chunks"),
            body={"size": 1, "query": {"term": {"accession_number": accession_number}}},
        )
    except Exception:  # noqa: BLE001
        return False
    hits = result.get("hits", {}).get("hits", [])
    return bool(hits)


def resolve_latest_from_lake(runtime: RuntimeClients, ticker: DemoTicker) -> FilingRef:
    """Resolve the newest lake filing that has readable provenance and index readiness."""
    cik = cik_for_ticker(ticker)
    accessions = _list_accessions(runtime.s3_client, runtime.bucket, cik)
    if not accessions:
        raise FileNotFoundError(f"no raw filings in lake for {ticker.value} cik={cik}")
    best: FilingRef | None = None
    readiness_misses: list[str] = []
    for accession in accessions:
        try:
            prov = load_provenance(runtime.s3_client, runtime.bucket, cik, accession)
        except Exception as exc:  # noqa: BLE001
            if _is_missing_object(exc):
                continue
            raise RuntimeError(
                f"failed loading provenance for {ticker.value} accession={accession}: {exc}"
            ) from exc
        if not _accession_indexed(runtime, prov["accession_number"]):
            readiness_misses.append(prov["accession_number"])
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
        if readiness_misses:
            raise FileNotFoundError(
                f"no indexed accession ready for emit for {ticker.value} under {prefix}; "
                f"seen provenance without index: {', '.join(readiness_misses)}"
            )
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
    include_key_events: bool = True,
) -> list[TickerEmitResult]:
    """Secondary re-emit for one or more tickers against the live lake/AOSS."""

    def resolve(ticker: DemoTicker) -> FilingRef:
        if accession:
            cik = cik_for_ticker(ticker)
            prov = load_provenance(runtime.s3_client, runtime.bucket, cik, accession)
            if not _accession_indexed(runtime, prov["accession_number"]):
                raise FileNotFoundError(
                    f"accession {accession} is not yet searchable in AOSS"
                )
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
        include_key_events=include_key_events,
    )
