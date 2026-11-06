# CLI contract: ingest helpers + secondary re-emit

Phase-1 operator CLI. Hermetic signal contract matches the HTTP re-emit API and the primary on-ingest Fargate path.
Research / decision-support only — not investment advice.

**Primary production path** is S3 raw object-created → Step Functions / Fargate (index + emit + curated Parquet).  
CLI `emit` is **re-emit / debug / backfill only**.

## Binary

```text
sec-signals
```

Python entrypoint from package `sec_signals.cli` (name may be configured in packaging; keep `sec-signals` as the documented UX name).

## Commands

### `sec-signals ingest`

Fetch latest 10-K / 10-K/A from EDGAR into the immutable S3 lake for tickers.
Landing a new raw object **starts** the primary index+emit+warehouse pipeline via S3 events.

```text
sec-signals ingest --tickers V,MA,PYPL,XYZ,COIN [--region eu-west-1]
```

### `sec-signals index`

Parse/chunk/embed/index from the raw lake into OpenSearch Serverless (Fargate job locally invoked or via Step Functions).
Ops helper for rebuild; primary path already indexes as part of on-ingest.

```text
sec-signals index --tickers V,MA,PYPL,XYZ,COIN [--rebuild]
```

`--rebuild` deletes derived vectors for those accessions and rebuilds from S3.
Does **not** by itself write warehouse signals unless combined with `emit` / primary pipeline.

### `sec-signals emit` (secondary)

Re-emit / backfill hermetic signals for demo tickers using the same library as on-ingest.
Writes curated Parquet (warehouse) by default; optional local JSON via `--out`.

```text
sec-signals emit --tickers V,MA,PYPL,XYZ,COIN [--out DIR] [--include-key-events/--no-include-key-events] [--accession ACCESSION] [--no-persist-warehouse]
```

| Flag | Required | Description |
|------|----------|-------------|
| `--tickers` | yes | Comma-separated subset of `V,MA,PYPL,XYZ,COIN` |
| `--out` | no | Directory for debug JSON files; default stdout (NDJSON or array) when set for local inspection |
| `--include-key-events` | no | Default true |
| `--accession` | no | Override latest filing selection |
| `--no-persist-warehouse` | no | Skip curated Parquet write (debug only; default is persist) |

**Exit codes**:
- `0` — all requested tickers emitted schema-valid payloads (and warehouse write succeeded when enabled)
- `2` — partial failure (some tickers errored; successful emissions still written)
- `3` — invalid arguments
- `4` — dependency failure (no usable index / Bedrock / S3 / Glue)

**Stdout / files**: Each successful emission MUST validate against `signal-emission.schema.json`.
Every emission includes `disclaimer` research-not-advice framing.
Durable analytics copy follows `contracts/signal-warehouse.md`.

### `sec-signals validate`

Validate a JSON file against `signal-emission.schema.json` and provenance rules.

```text
sec-signals validate --file path/to/emission.json
```

## Shared rules with API / primary path

- Closed factor catalog schema `0.1.0` only
- Validator drops uncited `ok` scores (emit `insufficient_evidence` with drop reason)
- `filing_date` required on emissions and warehouse partitions
- Same warehouse writer as Fargate on-ingest path
- No ranking / paper-broker / chat commands in Phase 1
- OpenSearch is RAG only — not the durable signal store
