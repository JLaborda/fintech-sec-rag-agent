"""Lambda HTTP handlers — secondary re-emit / backfill only."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from sec_signals.api.auth import UnauthorizedError, authorize_request
from sec_signals.aws.runtime import build_runtime
from sec_signals.models.enums import DemoTicker
from sec_signals.pipeline.batch_emit import FilingRef, batch_emit
from sec_signals.pipeline.cli_emit import resolve_latest_from_lake
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

    if "persist_warehouse" in body and not isinstance(body.get("persist_warehouse"), bool):
        return {
            "code": "invalid_request",
            "message": "persist_warehouse must be a boolean",
        }, 400
    persist_warehouse = body.get("persist_warehouse", True)
    if not isinstance(persist_warehouse, bool):
        persist_warehouse = True
    include_key_events = body.get("include_key_events", True)
    if not isinstance(include_key_events, bool):
        return {
            "code": "invalid_request",
            "message": "include_key_events must be a boolean",
        }, 400
    results = batch_emit(
        normalized,
        resolve_latest=resolve_latest,
        retriever=retriever,
        extractor=extractor,
        s3_client=s3_client,
        bucket=bucket,
        persist_warehouse=persist_warehouse,
        include_key_events=include_key_events,
    )
    payload_results = []
    for item in results:
        ticker_label = (
            item.ticker.value if hasattr(item.ticker, "value") else str(item.ticker)
        )
        entry: dict[str, Any] = {"ticker": ticker_label, "status": item.status}
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


def _json_response(status: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(payload),
    }


def _request_method(event: dict[str, Any]) -> str:
    return (event.get("requestContext", {}).get("http", {}) or {}).get("method") or event.get(
        "httpMethod", "GET"
    )


def _request_path(event: dict[str, Any]) -> str:
    return event.get("rawPath") or event.get("path") or ""


def lambda_handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    path = _request_path(event)
    method = _request_method(event)
    is_health = path.endswith("/v1/health") and method == "GET"

    # Health stays intentionally public (liveness); batch emit requires API key (+ IAM at GW).
    if not is_health:
        try:
            authorize_request(event)
        except UnauthorizedError as exc:
            return _json_response(401, {"code": "unauthorized", "message": str(exc)})

    if is_health:
        return _json_response(200, handle_health())

    if path.endswith("/v1/signals:batchEmit") and method == "POST":
        try:
            body = json.loads(event.get("body") or "{}")
        except json.JSONDecodeError:
            return _json_response(400, {"code": "invalid_request", "message": "body must be JSON"})
        if not isinstance(body, dict):
            return _json_response(
                400, {"code": "invalid_request", "message": "body must be a JSON object"}
            )
        if "persist_warehouse" in body and not isinstance(body.get("persist_warehouse"), bool):
            return _json_response(
                400,
                {
                    "code": "invalid_request",
                    "message": "persist_warehouse must be a boolean",
                },
            )
        try:
            runtime = build_runtime()
        except Exception as exc:  # noqa: BLE001 — surface wiring errors to caller
            return _json_response(
                503,
                {
                    "code": "runtime_unavailable",
                    "message": f"live AWS wiring unavailable: {exc}",
                },
            )

        def resolve(ticker: DemoTicker) -> FilingRef:
            return resolve_latest_from_lake(runtime, ticker)

        payload, status = handle_batch_emit(
            body,
            resolve_latest=resolve,
            retriever=runtime.retriever,
            extractor=runtime.extractor,
            s3_client=runtime.s3_client,
            bucket=runtime.bucket,
        )
        return _json_response(status, payload)

    return _json_response(404, {"code": "not_found", "message": f"no route for {method} {path}"})
