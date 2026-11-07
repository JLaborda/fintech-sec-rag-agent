# Quickstart validation: Phase-1 10-K signal demo

**Feature**: `001-10k-signal-demo` | **Region**: `eu-west-1` | **Date**: 2026-11-06

This guide validates the planned happy path end-to-end. It is a **run/validation** guide — not an implementation dump. Contracts: [`contracts/`](./contracts/). Data model: [`data-model.md`](./data-model.md). Decisions: [`research.md`](./research.md).

**Primary path**: new raw 10-K in S3 → Step Functions / Fargate (index + Haiku emit) → curated Parquet / Glue / Athena.  
**Secondary path**: CLI / API Gateway Lambda for re-emit, debug, and backfill only.

## Prerequisites

- AWS account with permissions for S3, OpenSearch Serverless, Bedrock (Converse + Titan embed), Step Functions, ECS/Fargate, ECR, Glue, Athena, Lambda, API Gateway, IAM, CloudWatch
- Bedrock model access enabled in `eu-west-1` for:
  - Embeddings: `amazon.titan-embed-text-v2:0`
  - Generation (via EU geo profile): `eu.anthropic.claude-haiku-4-5-20251001-v1:0`
- Terraform >= 1.5, Python 3.12, Docker (for Fargate image build)
- SEC EDGAR-compliant User-Agent identity configured (env / SSM — not committed)

## 1. Deploy happy path (Terraform)

```bash
cd infra/envs/demo
terraform init
terraform apply -var="aws_region=eu-west-1"
```

**Expected**: Outputs for raw lake bucket, curated signals prefix, Glue DB/table, Athena workgroup, AOSS endpoint/collection, primary state machine ARN, secondary re-emit API URL, pipeline version parameter.

## 2. Land a filing (starts primary path)

```bash
sec-signals ingest --tickers V,MA,PYPL,XYZ,COIN
```

**Expected**:
- Raw objects under `s3://…/raw/edgar/{cik}/{accession}/…` with provenance sidecar including `filing_date`
- S3 object-created events start Step Functions → Fargate for each new raw filing
- Pipeline: section-aware parse/chunk → Titan embed → AOSS upsert → retrieve → Haiku 4.5 extract → validate → **curated Parquet warehouse write**
- AOSS documents with filterable `filing_date`, `ticker`, `accession_number`, `section`/`item` (RAG only)
- Curated rows under `s3://…/curated/signals/factor_schema_version=0.1.0/ticker=…/filing_date=…/*.parquet`
- Athena (or Glue) can `SELECT` factor rows for a ticker/filing_date

Optional ops-only rebuild of vectors without re-emit:

```bash
sec-signals index --tickers V,MA,PYPL,XYZ,COIN --rebuild
```

## 3. Verify warehouse signals (primary success)

```bash
# Example — exact workgroup/DB names from Terraform outputs
aws athena start-query-execution \
  --query-string "SELECT ticker, filing_date, factor_id, status, polarity FROM sec_signals.curated_signals WHERE ticker = 'V' LIMIT 10" \
  --work-group "$ATHENA_WORKGROUP"
```

**Expected**:
- Five factor rows per emitted filing (closed catalog)
- `ok` rows have polarity ∈ [-1,1], conviction ∈ [0,1], citation columns; `insufficient_evidence` has null polarity
- `disclaimer` / research-not-advice present on rows
- Schema `factor_schema_version` = `0.1.0`

Local schema check against optional debug JSON (if written):

```bash
sec-signals validate --file /tmp/signals/V.json
```

## 4. Secondary re-emit / backfill (CLI — not primary)

```bash
sec-signals emit --tickers V,MA,PYPL,XYZ,COIN --out /tmp/signals
```

**Expected**: Same hermetic contract and warehouse writer as on-ingest; used for debug/backfill only. Exit codes per `contracts/cli-batch-emit.md`.

## 5. Secondary re-emit (API — not primary)

```bash
# Route requires IAM SigV4 + x-api-key (from SSM param demo_api_key_ssm_parameter).
# Example with awscurl (or AWS SDK signed request):
awscurl --service execute-api --region "$AWS_REGION" \
  -X POST "$EMIT_API_URL/v1/signals:batchEmit" \
  -H "content-type: application/json" \
  -H "x-api-key: $DEMO_API_KEY" \
  -d '{"tickers":["V","MA","PYPL","XYZ","COIN"]}'
```

**Expected**: HTTP 200 with per-ticker `emitted` results matching CLI contract fields (see `contracts/batch-emit.openapi.yaml`). Anonymous/`curl` without SigV4 is rejected at API Gateway. Does **not** replace the S3→Fargate primary path.

## 6. Contract tests (always)

```bash
pytest tests/contract -q
```

**Expected**: Schema, provenance, warehouse row shape, and `insufficient_evidence` fixtures pass; uncited scored claims are dropped.

## 7. LLM-as-judge (RAG-change CI only)

When retrieval, prompts, factor schema, or signal pipeline change:

```bash
pytest tests/golden -q -m llm_judge
```

**Expected**: Golden set runs via Bedrock; failures block merge. Unrelated doc-only changes do **not** require this marker.

## 8. Negative checks (scope)

- No endpoints or CLI commands for ranking, portfolio alerts, or paper broker
- Ingest rejects or ignores 10-Q / 8-K / news sources
- No chat-first UX surface in demo deploy
- Durable signals are **not** solely stored in OpenSearch

## Success mapping

| Quickstart step | Spec success criteria |
|-----------------|----------------------|
| 2–3 on-ingest + warehouse | SC-001, SC-002, SC-003, SC-006 |
| 1 deploy + 2–3 | SC-004 |
| 4–5 secondary re-emit | Operator backfill / parity with primary contract |
| 6–7 CI gates | SC-005 |
