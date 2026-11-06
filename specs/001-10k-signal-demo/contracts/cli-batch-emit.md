# CLI contract: batch emit & ingest helpers

Phase-1 operator CLI for the same hermetic signal contract as the HTTP API.
Research / decision-support only — not investment advice.

## Binary

```text
sec-signals
```

Python entrypoint from package `sec_signals.cli` (name may be configured in packaging; keep `sec-signals` as the documented UX name).

## Commands

### `sec-signals emit`

Batch-emit hermetic signals for demo tickers.

```text
sec-signals emit --tickers V,MA,PYPL,XYZ,COIN [--out DIR] [--include-key-events/--no-include-key-events] [--accession ACCESSION]
```

| Flag | Required | Description |
|------|----------|-------------|
| `--tickers` | yes | Comma-separated subset of `V,MA,PYPL,XYZ,COIN` |
| `--out` | no | Directory for JSON files; default stdout (NDJSON or array) |
| `--include-key-events` | no | Default true |
| `--accession` | no | Override latest filing selection |

**Exit codes**:
- `0` — all requested tickers emitted schema-valid payloads
- `2` — partial failure (some tickers errored; successful emissions still written)
- `3` — invalid arguments
- `4` — dependency failure (no usable index / Bedrock / S3)

**Stdout / files**: Each successful emission MUST validate against `signal-emission.schema.json`.
Every emission includes `disclaimer` research-not-advice framing.

### `sec-signals ingest`

Fetch latest 10-K / 10-K/A from EDGAR into the immutable S3 lake for tickers.

```text
sec-signals ingest --tickers V,MA,PYPL,XYZ,COIN [--region eu-west-1]
```

### `sec-signals index`

Parse/chunk/embed/index from the raw lake into OpenSearch Serverless (Fargate job locally invoked or via Step Functions).

```text
sec-signals index --tickers V,MA,PYPL,XYZ,COIN [--rebuild]
```

`--rebuild` deletes derived vectors for those accessions and rebuilds from S3.

### `sec-signals validate`

Validate a JSON file against `signal-emission.schema.json` and provenance rules.

```text
sec-signals validate --file path/to/emission.json
```

## Shared rules with API

- Closed factor catalog schema `0.1.0` only
- Validator drops uncited `ok` scores (emit `insufficient_evidence` with drop reason)
- `filing_date` required on emissions
- No ranking / paper-broker / chat commands in Phase 1
