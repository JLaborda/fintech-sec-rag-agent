# Quickstart validation: Phase-1 10-K signal demo

**Feature**: `001-10k-signal-demo` | **Region**: `eu-west-1` | **Date**: 2026-11-06

This guide validates the planned happy path end-to-end. It is a **run/validation** guide — not an implementation dump. Contracts: [`contracts/`](./contracts/). Data model: [`data-model.md`](./data-model.md). Decisions: [`research.md`](./research.md).

## Prerequisites

- AWS account with permissions for S3, OpenSearch Serverless, Bedrock (Converse + Titan embed), Lambda, API Gateway, Step Functions, ECS/Fargate, ECR, IAM, CloudWatch
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

**Expected**: Outputs for raw lake bucket, signals prefix, AOSS endpoint/collection, emit API URL, ingest/index state machine ARN, pipeline version parameter.

## 2. Ingest + index demo universe

```bash
sec-signals ingest --tickers V,MA,PYPL,XYZ,COIN
sec-signals index --tickers V,MA,PYPL,XYZ,COIN
```

**Expected**:
- Raw objects under `s3://…/raw/edgar/{cik}/{accession}/…` with provenance sidecar including `filing_date`
- AOSS documents with filterable `filing_date`, `ticker`, `accession_number`, `section`/`item`
- Re-run `sec-signals index --rebuild` after deleting vectors still succeeds from lake alone

## 3. Batch emit (CLI)

```bash
sec-signals emit --tickers V,MA,PYPL,XYZ,COIN --out /tmp/signals
```

**Expected**:
- Five JSON files (or fewer only if a ticker truly has no usable filing — those must error clearly)
- Each file validates: `sec-signals validate --file /tmp/signals/V.json`
- Schema `factor_schema_version` = `0.1.0`; exactly five catalog factors
- `ok` factors have polarity ∈ [-1,1], conviction ∈ [0,1], citation quote; `insufficient_evidence` has no polarity
- `disclaimer` present (research-not-advice)

## 4. Batch emit (API)

```bash
curl -s -X POST "$EMIT_API_URL/v1/signals:batchEmit" \
  -H "content-type: application/json" \
  -H "x-api-key: $DEMO_API_KEY" \
  -d '{"tickers":["V","MA","PYPL","XYZ","COIN"]}'
```

**Expected**: HTTP 200 with per-ticker `emitted` results matching CLI contract fields (see `contracts/batch-emit.openapi.yaml`).

## 5. Contract tests (always)

```bash
pytest tests/contract -q
```

**Expected**: Schema, provenance, and `insufficient_evidence` fixtures pass; uncited scored claims are dropped.

## 6. LLM-as-judge (RAG-change CI only)

When retrieval, prompts, factor schema, or signal pipeline change:

```bash
pytest tests/golden -q -m llm_judge
```

**Expected**: Golden set runs via Bedrock; failures block merge. Unrelated doc-only changes do **not** require this marker.

## 7. Negative checks (scope)

- No endpoints or CLI commands for ranking, portfolio alerts, or paper broker
- Ingest rejects or ignores 10-Q / 8-K / news sources
- No chat-first UX surface in demo deploy

## Success mapping

| Quickstart step | Spec success criteria |
|-----------------|----------------------|
| 3–4 emit | SC-001, SC-002, SC-003, SC-006 |
| 1 deploy + 3 emit | SC-004 |
| 5–6 CI gates | SC-005 |
