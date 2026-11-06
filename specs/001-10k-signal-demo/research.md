# Research: Phase-1 SEC 10-K Qualitative Signal Generator

**Feature**: `001-10k-signal-demo` | **Date**: 2026-11-06

All Technical Context unknowns resolved. No remaining `NEEDS CLARIFICATION`.

## Decision 1: AWS Region

**Decision**: Primary region **`eu-west-1` (Ireland)**.

**Rationale**:
- Preferred by product brief when Bedrock models are available there.
- Amazon Titan Text Embeddings V2 (`amazon.titan-embed-text-v2:0`) supports in-region inference in `eu-west-1`.
- Claude Sonnet 4.5 is reachable from `eu-west-1` via the **EU geo inference profile** (routes within EU destination regions).
- Keeps raw S3 lake, OpenSearch Serverless, and Lambda/Fargate co-located for a simple Terraform happy path.

**Alternatives considered**:
- `us-east-1`: Broadest Bedrock catalog and often default for tutorials; rejected as primary because `eu-west-1` meets model needs and matches preferred residency.
- Multi-region active-active: unnecessary for five-ticker demo.

## Decision 2: Generation LLM (Bedrock Converse)

**Decision**: **Amazon Bedrock Converse** with **Claude Sonnet 4.5** via EU geo inference profile:

| Field | Value |
|-------|-------|
| API | `bedrock-runtime` `Converse` |
| Base model ID | `anthropic.claude-sonnet-4-5-20250929-v1:0` |
| Runtime `modelId` (eu-west-1) | `eu.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| Client region | `eu-west-1` |
| Use | Factor extraction, optional `key_events`, LLM-as-judge in CI |

**Rationale**:
- Brief asked for “Claude Sonnet 4 (or current Sonnet available)”. **Claude Sonnet 4 (`anthropic.claude-sonnet-4-20250514-v1:0`) reached EOL on 2026-10-14** and now fails with `ResourceNotFoundException`.
- Sonnet 4.5 is the current Sonnet-class model for this use case (Legacy stage; EOL 2027-04-08) with Converse support and structured-output capability suitable for hermetic JSON.
- EU geo profile from `eu-west-1` keeps inference within EU geography while remaining AWS-native.

**Alternatives considered**:
- Claude Sonnet 4: EOL — cannot use.
- Claude Haiku 4.5: cheaper/faster; weaker for grounded multi-factor extraction with citations — reserve as optional cost-down later, not Phase-1 default.
- Non-Bedrock LLMs: violates constitution AWS/Bedrock constraint.

## Decision 3: Embeddings

**Decision**: **Amazon Titan Text Embeddings V2** on Bedrock.

| Field | Value |
|-------|-------|
| Model ID | `amazon.titan-embed-text-v2:0` |
| Dimensions | **1024** (default; normalize=true) |
| Region | `eu-west-1` in-region |
| Max input | 8,192 tokens / chunk |

**Rationale**: AWS-native, available in `eu-west-1`, configurable dimensions, standard for Bedrock RAG demos, no third-party embedding vendor.

**Alternatives considered**:
- Cohere Embed on Bedrock: viable; adds another provider relationship without Phase-1 benefit.
- Titan Embeddings G1: older; V2 preferred for retrieval quality.

## Decision 4: Vector store

**Decision**: **Amazon OpenSearch Serverless** — **Vector search** collection in `eu-west-1`.

**Index design (logical)**:
- k-NN vector field (1024-dim, cosine/inner-product per Titan normalize settings).
- Filterable metadata fields: `ticker`, `cik`, `accession_number`, `form`, **`filing_date`**, `section` / `item`, `chunk_id`, offsets when present.
- Collection treated as **derived** — rebuildable from S3 raw lake.

**Rationale**:
- Brief preference for OpenSearch Serverless for managed vector RAG demo.
- Native metadata filtering for `filing_date` and ticker/accession provenance at retrieve time.
- No always-on Aurora cluster to operate for five tickers.

**Alternatives considered**:
- **Aurora PostgreSQL + pgvector**: simpler SQL mental model and often cheaper at tiny scale, but requires VPC/RDS ops and is less “managed RAG vector collection” than AOSS for the demo narrative. Rejected as primary; acceptable fallback if AOSS account limits block demo.
- Bedrock Knowledge Bases managed store: hides chunk metadata control needed for constitution provenance; keep custom ingest→index path.

## Decision 5: Compute & runtime topology

**Decision**: **Split by workload**:

| Workload | Runtime | Why |
|----------|---------|-----|
| Batch emit API | **API Gateway HTTP API → Lambda (Python 3.12)** | Retrieval + Converse + validate fits demo latency/memory; simplest operator surface |
| Local/ops CLI | **Python CLI** sharing the same library as Lambda | Same hermetic contract; can call library locally or invoke API |
| EDGAR fetch → S3 | **Lambda** (per ticker) | Small network+write job |
| Section-aware parse / chunk / embed / AOSS index | **ECS Fargate task** (Python) orchestrated by **Step Functions** | Full 10-K HTML can exceed comfortable Lambda time/memory; Fargate avoids 15-minute cliff |
| Rebuild index from lake | Same Fargate task | Constitution: indexes derived/rebuildable |

**Rationale**: Matches “prefer Lambda + S3 where feasible; Fargate when parse exceeds Lambda limits.” Emit path stays Lambda-simple; heavy document processing uses Fargate.

**Alternatives considered**:
- All-Lambda: possible for five tickers with careful streaming, but brittle for large HTML + many embed calls — rejected as sole path.
- Always-on ECS service: unnecessary cost for batch demo.
- AWS Batch: workable; Fargate task via Step Functions is enough and simpler for Terraform happy path.

## Decision 6: Language, packaging, IaC

**Decision**:
- **Python 3.12** (constitution: Python primary).
- Packaging: `src/` layout installable package + Lambda container or zip with shared code; Fargate image from same package.
- **Terraform** modules under `infra/` for S3, AOSS, IAM, API Gateway, Lambda, Step Functions, ECR, Fargate task definition, CloudWatch logs.
- Config via environment / SSM Parameter Store (no secrets in repo).

**Alternatives considered**: SAM/CDK-only — Terraform is constitution-canonical.

## Decision 7: EDGAR ingest approach

**Decision**:
- Use SEC EDGAR company submissions / full-text endpoints with a registered User-Agent per SEC fair-access guidance.
- Resolve ticker → CIK for V, MA, PYPL, XYZ, COIN; select **latest** `10-K` or `10-K/A` by `filing_date`.
- Store **immutable raw** object in S3: `s3://{bucket}/raw/edgar/{cik}/{accession_number}/...` plus a small JSON sidecar of provenance (`ticker`, `cik`, `accession_number`, `form`, `filing_date`, source URLs).
- Never mutate raw objects; new accessions are new keys.

**Alternatives considered**: Third-party filing APIs — rejected; EDGAR is canonical per constitution.

## Decision 8: Parse / chunk strategy

**Decision**:
- Prefer HTML primary document from the filing submission; fall back to plain text if needed.
- Section-aware segmentation by 10-K **Item** headings (e.g. Item 1, 1A, 7, 7A, 8) with `section`/`item` metadata on every chunk.
- Chunk size tuned to Titan V2 context (target ~500–1,000 tokens with overlap); store character offsets when available for citations.
- Every chunk metadata **must** include `filing_date`.

**Alternatives considered**: Naive fixed-size chunking only — insufficient for citation quality; pure LLM section tagging — slower/costlier for demo.

## Decision 9: Signal extraction & validation

**Decision**:
- Per ticker: retrieve top-k chunks **per factor** (metadata filter on ticker/accession + semantic query for factor definition).
- Single Converse call (or five factor-scoped calls if context pressure) producing hermetic JSON for schema `0.1.0`.
- **JSON Schema validator** post-model: drop any `ok` factor lacking citation/provenance; coerce illegal polarity; require `insufficient_evidence` without polarity when evidence gap.
- Persist emissions under `s3://{bucket}/signals/{factor_schema_version}/{ticker}/{accession_number}/{pipeline_version}.json`.

**Alternatives considered**: Free-form chat agent — out of scope; unvalidated LLM JSON — violates constitution gates.

## Decision 10: Quality gates & CI

**Decision**:
- **Always**: pytest contract tests + fixtures (schema, provenance, `insufficient_evidence`).
- **When RAG surfaces change** (path filters on retrieval/prompts/schema/pipeline): LLM-as-judge golden set via Bedrock Converse (same Sonnet 4.5 profile or Haiku for cost — default Sonnet 4.5 for judge consistency in Phase 1).
- Judge **not** on every production emit request.

**Alternatives considered**: Judge on every request — constitution forbids for v1 cost/latency.

## Decision 11: Auth & API surface

**Decision**:
- HTTP API with **IAM SigV4** and/or API key for internal demo (Terraform-configurable); not public anonymous.
- CLI uses same request/response contract as API (`contracts/signal-emission.schema.json`, `contracts/batch-emit.openapi.yaml`).
- All responses include research-not-advice framing field or standard disclaimer string.

**Alternatives considered**: Cognito user pools — overkill for Phase-1 demo.

## Sources (docs consulted)

- AWS Bedrock model card: Claude Sonnet 4 (EOL 2026-10-14)
- AWS Bedrock model card: Claude Sonnet 4.5 (`anthropic.claude-sonnet-4-5-20250929-v1:0`, EU geo `eu.anthropic.claude-sonnet-4-5-20250929-v1:0`)
- AWS Bedrock model card: Titan Text Embeddings V2 (`amazon.titan-embed-text-v2:0`)
- Project constitution v1.0.0; phase-1 signal contract v0.1; `specs/001-10k-signal-demo/spec.md`
