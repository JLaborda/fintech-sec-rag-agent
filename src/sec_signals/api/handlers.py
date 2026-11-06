"""Lambda HTTP handlers — secondary re-emit / backfill only."""

from __future__ import annotations

import json
from typing import Any, Callable

from sec_signals.api.auth import UnauthorizedError, authorize_request
from sec_signals.models.enums import DemoTicker
from sec_signals.pipeline.batch_emit import FilingRef, batch_emit
from sec_signals.pipeline.emit import DISCLAIMER

ResolveLatest = Callable[[DemoTicker], FilingRef]


def handle_health() -> dict[str, str]:
    return {"status": "ok"}


def handle_batch_emit(
    body: dict[str, Any],
    *,
    resolve_latest: ResolveLatest,
    retriever: Any,
    extractor: Any,
    s3_client: Any,
    bucket: str,
) -> tuple[dict[str, Any], int]:
    tickers = body.get("tickers")
    if not isinstance(tickers, list) or not tickers or len(tickers) > 5:
        return {"code": "invalid_request", "message": "tickers must be 1..5 demo tickers"}, 400
    try:
        normalized = [DemoTicker(t) for t in tickers]
    except Exception:  # noqa: BLE001
        return {"code": "invalid_request", "message": "unknown ticker in request"}, 400
    if len(set(normalized)) != len(normalized):
        return {"code": "invalid_request", "message": "tickers must be unique"}, 400

    persist_warehouse = bool(body.get("persist_warehouse", True))
    results = batch_emit(
        normalized,
        resolve_latest=resolve_latest,
        retriever=retriever,
        extractor=extractor,
        s3_client=s3_client,
        bucket=bucket,
        persist_warehouse=persist_warehouse,
    )
    payload_results = []
    for item in results:
        entry: dict[str, Any] = {"ticker": item.ticker.value, "status": item.status}
        if item.status == "emitted" and item.emission is not None:
            entry["emission"] = item.emission.model_dump(mode="json")
            entry["warehouse_uri"] = item.warehouse_uri
        else:
            entry["error"] = {
                "code": item.error_code or "emit_failed",
                "message": item.error_message or "unknown error",
            }
        payload_results.append(entry)
    return {"disclaimer": DISCLAIMER, "results": payload_results}, 200


def lambda_handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    try:
        authorize_request(event)
    except UnauthorizedError as exc:
        return {
            "statusCode": 401,
            "headers": {"content-type": "application/json"},
            "body": json.dumps({"code": "unauthorized", "message": str(exc)}),
        }

    path = event.get("rawPath") or event.get("path") or ""
    method = (event.get("requestContext", {}).get("http", {}) or {}).get("method") or event.get(
        "httpMethod", "GET"
    )
    if path.endswith("/v1/health") and method == "GET":
        return {
            "statusCode": 200,
            "headers": {"content-type": "application/json"},
            "body": json.dumps(handle_health()),
        }
    return {
        "statusCode": 404,
        "headers": {"content-type": "application/json"},
        "body": json.dumps({"code": "not_found", "message": f"no route for {method} {path}"}),
    }
