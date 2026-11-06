# Research: Phase-1 SEC 10-K Qualitative Signal Generator

**Feature**: `001-10k-signal-demo` | **Date**: 2026-11-06

All Technical Context unknowns resolved. No remaining `NEEDS CLARIFICATION`.

## Decision 1: AWS Region

**Decision**: Primary region **`eu-west-1` (Ireland)**.

**Rationale**:
- Preferred by product brief when Bedrock models are available there.
- Amazon Titan Text Embeddings V2 (`amazon.titan-embed-text-v2:0`) supports in-region inference in `eu-west-1`.
- Claude Haiku 4.5 is reachable from `eu-west-1` via the **EU geo inference profile** (routes within EU destination regions).
- Keeps raw S3 lake, curated Parquet, OpenSearch Serverless, Glue/Athena, and Fargate co-located for a simple Terraform happy path.

**Alternatives considered**:
- `us-east-1`: Broadest Bedrock catalog and often default for tutorials; rejected as primary because `eu-west-1` meets model needs and matches preferred residency.
- Multi-region active-active: unnecessary for five-ticker demo.

## Decision 2: Generation LLM (Bedrock Converse)

**Decision**: **Amazon Bedrock Converse** with **Claude Haiku 4.5** via EU geo inference profile:

| Field | Value |
|-------|-------|
| API | `bedrock-runtime` `Converse` |
| Foundation model (reference) | `anthropic.claude-haiku-4-5-20251001-v1:0` |
| Runtime `modelId` (eu-west-1) | `eu.anthropic.claude-haiku-4-5-20251001-v1:0` |
| Client region | `eu-west-1` |
| Use | Factor extraction (on-ingest primary + re-emit), optional `key_events`, LLM-as-judge in CI |
| Approx. EU on-demand rates | **~$1.10 / 1M input tokens**, **~$5.50 / 1M output tokens** (≈ **$0.0011 / 1K in**, **$0.0055 / 1K out**) |

> Note: On `bedrock-runtime`, Haiku 4.5 requires a geo/global inference profile ID (bare foundation model ID is not supported for on-demand). Phase-1 uses the EU geo profile from `eu-west-1`.

**Rationale**:
- **Demo cost savings**: Haiku 4.5 is substantially cheaper than Sonnet-class models for repeated extract + CI judge runs on a five-ticker universe.
- **Adequate for hermetic JSON signals**: structured Converse output + mandatory JSON Schema / provenance validator + contract fixtures + LLM-as-judge golden set on RAG changes keep quality gates intact even if raw generative strength is below Sonnet.
- EU geo profile from `eu-west-1` keeps inference within EU geography while remaining AWS-native.
- Active Bedrock model (launch 2025-10-16) with Converse and structured-output support.

**Alternatives considered**:
- Claude Sonnet 4: EOL (2026-10-14) — cannot use.
- Claude Sonnet 4.5 (`eu.anthropic.claude-sonnet-4-5-20250929-v1:0`): stronger reasoning but higher demo cost; superseded as Phase-1 default in favor of Haiku 4.5 with schema validation + evals compensating for lighter model class.
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

## Decision 4: Vector store (RAG only — not durable signals)

**Decision**: **Amazon OpenSearch Serverless** — **Vector search** collection in `eu-west-1`.

**Index design (logical)**:
- k-NN vector field (1024-dim, cosine/inner-product per Titan normalize settings).
- Filterable metadata fields: `ticker`, `cik`, `accession_number`, `form`, **`filing_date`**, `section` / `item`, `chunk_id`, offsets when present.
- Collection treated as **derived** — rebuildable from S3 raw lake.
- **Role**: retrieval surface during Haiku signal generation only. **NOT** the durable signal store.

**Rationale**:
- Brief preference for OpenSearch Serverless for managed vector RAG demo.
- Native metadata filtering for `filing_date` and ticker/accession provenance at retrieve time.
- No always-on Aurora cluster to operate for five tickers.
- Separating RAG index from warehouse avoids treating k-NN documents as analytics tables.

**Alternatives considered**:
- **Aurora PostgreSQL + pgvector**: simpler SQL mental model and often cheaper at tiny scale, but requires VPC/RDS ops and is less “managed RAG vector collection” than AOSS for the demo narrative. Rejected as primary; acceptable fallback if AOSS account limits block demo.
- Bedrock Knowledge Bases managed store: hides chunk metadata control needed for constitution provenance; keep custom ingest→index path.
- Storing durable signals inside AOSS: rejected — wrong store shape for DataFrame → warehouse / Athena analytics.

## Decision 5: Compute & runtime topology (locked — on-ingest primary)

**Decision**: **Primary production path is on-ingest emit; CLI/API are secondary**.

| Workload | Runtime | Role |
|----------|---------|------|
| New raw 10-K / 10-K/A object in S3 lake | **S3 Event Notification → Step Functions → ECS Fargate** | **PRIMARY**: parse/chunk → Titan embed → AOSS index → retrieve → Haiku extract → validate → **warehouse Parquet write** |
| Rebuild index from lake (ops) | Same Fargate task (index-only / rebuild mode) | Constitution: indexes derived/rebuildable |
| EDGAR fetch → S3 (bootstrap / scheduled) | **Lambda** or CLI-triggered fetch writing immutable raw keys | Landing a new raw object **starts** the primary path |
| Re-emit / debug / backfill | **API Gateway HTTP API → Lambda** + **Python CLI** | **SECONDARY only** — same library as Fargate emit; does **not** replace on-ingest |

**Rationale**:
- User-locked architecture (choice A): when a filing lands, the pipeline MUST index, immediately generate hermetic signal JSON, and persist into a tabular warehouse path suitable for later analytics.
- Fargate via Step Functions avoids Lambda’s 15-minute cliff for full HTML parse + many embed + Converse calls in one shot.
- Keeping Lambda/CLI as reprocess surfaces preserves operator ergonomics without making on-demand HTTP the production truth.
- Matches “prefer Lambda + S3 where feasible; Fargate when parse exceeds Lambda limits,” with emit folded into the heavy path.

**Alternatives considered**:
- **On-demand Lambda/CLI as primary emit** (prior plan): rejected by locked product decision — production truth is on-ingest.
- All-Lambda primary: brittle for large HTML + embed + Converse in one invocation.
- Always-on ECS service: unnecessary cost for batch demo.
- AWS Batch: workable; Step Functions + Fargate is enough and simpler for Terraform happy path.

## Decision 6: Durable signal store / warehouse path (locked)

**Decision**: **S3 curated Parquet + AWS Glue Data Catalog + Amazon Athena** in `eu-west-1`.

| Layer | Choice |
|-------|--------|
| Write shape | Validated `SignalEmission` → **tabular rows** (factor-grain preferred for analytics; see `data-model.md`) via pandas/pyarrow |
| Object layout | `s3://{bucket}/curated/signals/factor_schema_version={0.1.0}/ticker={TICKER}/filing_date={YYYY-MM-DD}/…parquet` |
| Partitioning | Hive-style **`ticker`** + **`filing_date`** (plus schema version prefix for contract evolution) |
| Catalog | **AWS Glue** table `sec_signals.curated_signals` (or equivalent DB/table names in Terraform) |
| Query / warehouse UX | **Amazon Athena** (SQL over curated Parquet) — lightweight demo warehouse |
| Debug optional | JSON under `s3://{bucket}/signals/{factor_schema_version}/{ticker}/{accession}/{pipeline_version}.json` — **not** the durable analytics store |

**Rationale**:
- Treats signals as **DataFrame → data warehouse** from day one, aligning with the north-star analytics stage without standing up Redshift/Snowflake for five tickers.
- Fully AWS-native, Terraform-friendly, low fixed cost (pay-per-query Athena + S3 storage).
- Partitioning by `ticker` / `filing_date` matches operator filters and later ranking joins.
- OpenSearch stays free to rebuild; curated Parquet is the **authoritative durable signal record** for Phase-1 consumers and future ranking.

**Alternatives considered**:
- **JSON-only under `signals/`**: fine for debug; poor tabular warehouse / Athena story — rejected as sole durable store.
- **Amazon Redshift / Redshift Serverless**: true warehouse but heavy for demo ops/cost.
- **DynamoDB**: not a DataFrame → warehouse path; awkward for Athena-style analytics.
- **AOSS as signal store**: rejected — RAG index ≠ durable analytics table.
- **RDS/PostgreSQL**: workable SQL, but Glue/Athena over Parquet better matches lakehouse narrative and avoids always-on DB for the demo.

## Decision 7: Language, packaging, IaC

**Decision**:
- **Python 3.12** (constitution: Python primary).
- Packaging: `src/` layout installable package + Fargate image from same package; Lambda zip/container shares library for re-emit only.
- **Terraform** modules under `infra/` for S3 (raw + curated), Glue catalog/table, Athena workgroup, AOSS, IAM, S3→Step Functions→Fargate, secondary API Gateway + Lambda, ECR, CloudWatch logs.
- Config via environment / SSM Parameter Store (no secrets in repo).

**Alternatives considered**: SAM/CDK-only — Terraform is constitution-canonical.

## Decision 8: EDGAR ingest approach

**Decision**:
- Use SEC EDGAR company submissions / full-text endpoints with a registered User-Agent per SEC fair-access guidance.
- Resolve ticker → CIK for V, MA, PYPL, XYZ, COIN; select **latest** `10-K` or `10-K/A` by `filing_date`.
- Store **immutable raw** object in S3: `s3://{bucket}/raw/edgar/{cik}/{accession_number}/...` plus a small JSON sidecar of provenance (`ticker`, `cik`, `accession_number`, `form`, `filing_date`, source URLs).
- Never mutate raw objects; new accessions are new keys.
- **Object-created events on the raw prefix start the primary index+emit+warehouse pipeline.**

**Alternatives considered**: Third-party filing APIs — rejected; EDGAR is canonical per constitution.

## Decision 9: Parse / chunk strategy

**Decision**:
- Prefer HTML primary document from the filing submission; fall back to plain text if needed.
- Section-aware segmentation by 10-K **Item** headings (e.g. Item 1, 1A, 7, 7A, 8) with `section`/`item` metadata on every chunk.
- Chunk size tuned to Titan V2 context (target ~500–1,000 tokens with overlap); store character offsets when available for citations.
- Every chunk metadata **must** include `filing_date`.

**Alternatives considered**: Naive fixed-size chunking only — insufficient for citation quality; pure LLM section tagging — slower/costlier for demo.

## Decision 10: Signal extraction, validation & persistence

**Decision**:
- On new raw filing (primary) or re-emit request (secondary): retrieve top-k chunks **per factor** (metadata filter on ticker/accession + semantic query for factor definition) from AOSS.
- Single Converse call (or five factor-scoped calls if context pressure) producing hermetic JSON for schema `0.1.0`.
- **JSON Schema validator** post-model: drop any `ok` factor lacking citation/provenance; coerce illegal polarity; require `insufficient_evidence` without polarity when evidence gap.
- Persist durable rows to **curated Parquet / Glue** per Decision 6; optionally also write debug JSON under `signals/`.

**Alternatives considered**: Free-form chat agent — out of scope; unvalidated LLM JSON — violates constitution gates; persist-only-to-AOSS — rejected (Decision 4/6).

## Decision 11: Quality gates & CI

**Decision**:
- **Always**: pytest contract tests + fixtures (schema, provenance, `insufficient_evidence`, warehouse row shape).
- **When RAG surfaces change** (path filters on retrieval/prompts/schema/pipeline): LLM-as-judge golden set via Bedrock Converse using the **same Haiku 4.5 EU geo profile** as extraction (cost-aligned; consistency with emit path).
- Judge **not** on every production emit (including on-ingest emits).

**Alternatives considered**: Judge on every request — constitution forbids for v1 cost/latency.

## Decision 12: Auth & secondary API/CLI surface

**Decision**:
- HTTP API with **IAM SigV4** and/or API key for internal demo (Terraform-configurable); not public anonymous.
- CLI and API are **re-emit / debug / backfill** only; same request/response contract (`contracts/signal-emission.schema.json`, `contracts/batch-emit.openapi.yaml`) and same warehouse writer as the primary path.
- All emissions include research-not-advice framing field or standard disclaimer string.

**Alternatives considered**: Cognito user pools — overkill for Phase-1 demo; treating HTTP batch emit as primary production — rejected by locked architecture.

## Sources (docs consulted)

- AWS Bedrock model card: Claude Haiku 4.5 (EU geo `eu.anthropic.claude-haiku-4-5-20251001-v1:0`)
- AWS Bedrock model card: Claude Sonnet 4 (EOL 2026-10-14) — historical context only
- AWS Bedrock model card: Claude Sonnet 4.5 — considered then rejected as Phase-1 default for cost
- AWS Bedrock model card: Titan Text Embeddings V2 (`amazon.titan-embed-text-v2:0`) — unchanged
- AWS Glue / Athena / S3 Parquet lakehouse patterns for curated analytics tables
- Project constitution v1.0.0; phase-1 signal contract v0.1; `specs/001-10k-signal-demo/spec.md`
- Locked architecture choice A (on-ingest emit + warehouse durable store; AOSS = RAG only)
