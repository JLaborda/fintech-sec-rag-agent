# Contract: durable signal warehouse persistence

Phase-1 durable store for hermetic qualitative signals after validation.
OpenSearch Serverless is **not** this store — it is RAG retrieval only.

Research / decision-support only — not investment advice.

## Purpose

When a `SignalEmission` passes schema/provenance validation (primary on-ingest path or secondary re-emit), the pipeline MUST flatten it to tabular rows and persist them for later warehouse / analytics processing (DataFrame → lakehouse).

## Technology (locked for demo)

| Concern | Choice |
|---------|--------|
| File format | Apache Parquet (Snappy or ZSTD) |
| Object prefix | `s3://{bucket}/curated/signals/` |
| Partitions | `factor_schema_version`, **`ticker`**, **`filing_date`** |
| Catalog | AWS Glue Data Catalog |
| SQL access | Amazon Athena |
| Region | `eu-west-1` |

See `research.md` Decision 6 and `data-model.md` entity `SignalFactorRow`.

## Object key layout

```text
s3://{bucket}/curated/signals/
  factor_schema_version=0.1.0/
    ticker={TICKER}/
      filing_date={YYYY-MM-DD}/
        part-{accession_number_sanitized}-{pipeline_version}.parquet
```

- `{TICKER}` ∈ `V|MA|PYPL|XYZ|COIN`
- `{YYYY-MM-DD}` = emission / filing `filing_date`
- One Parquet file contains **exactly five** factor rows for that emission natural key

## Row contract

Each row MUST include columns defined for `SignalFactorRow` in `data-model.md`:

- Identity / provenance: `factor_schema_version`, `ticker`, `filing_date`, `cik`, `accession_number`, `form`, `model_or_pipeline_version`, `emitted_at`
- Factor: `factor_id`, `status`, `polarity` (null if `insufficient_evidence`), `conviction`, citation columns, `reasoning`
- Framing: `disclaimer` (non-empty research-not-advice)
- Optional: `key_events_json`

### Validation before write

1. Source object MUST validate against `signal-emission.schema.json`.
2. Exactly five rows; `factor_id` set equals the closed catalog.
3. Partition values MUST match row column values for `ticker` and `filing_date`.
4. Writers MUST NOT publish partial factor sets for a successful emission.

### Idempotency

- Natural key: `(ticker, accession_number, factor_schema_version, model_or_pipeline_version)`.
- Prefer a new `model_or_pipeline_version` for reprocess so history remains auditable.
- Overwriting the same key’s Parquet object is allowed for crash recovery of an identical version.

## Glue table (logical)

| Property | Value |
|----------|-------|
| Database | `sec_signals` (Terraform-overridable) |
| Table | `curated_signals` |
| Input format | Parquet |
| Partition keys | `factor_schema_version`, `ticker`, `filing_date` |

Athena consumers query this table; they MUST NOT treat AOSS as the signal warehouse.

## Non-goals

- Ranking / portfolio tables
- Mutating raw EDGAR objects
- Using OpenSearch documents as durable signal rows
- Requiring Redshift or an always-on RDBMS for Phase-1 demo

## Relationship to secondary emit API/CLI

`POST /v1/signals:batchEmit` and `sec-signals emit` MUST use the **same** warehouse writer as the primary Fargate path. They are re-emit / debug / backfill only — success still means curated Parquet (+ optional debug JSON), not AOSS-only persistence.
