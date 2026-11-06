# Implementation Plan: Phase-1 SEC 10-K Qualitative Signal Generator

**Branch**: `001-10k-signal-demo` | **Date**: 2026-11-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-10k-signal-demo/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Deliver an AWS-native horizontal slice that ingests the latest SEC **10-K / 10-K/A** for tickers **V, MA, PYPL, XYZ, COIN** into an immutable **S3** lake, section-aware chunks with **`filing_date`** metadata into **OpenSearch Serverless**, embeds with **Titan Text Embeddings V2**, and — **on every new raw filing landing in the lake** — immediately extracts hermetic qualitative signals via **Bedrock Converse (Claude Haiku 4.5, EU geo profile)** under locked contract schema **`0.1.0`**, validates/drops uncited scores, and **persists durable signals into a tabular warehouse path** (S3 Parquet curated zone + Glue Catalog + Athena). OpenSearch remains the **RAG vector index for retrieval during generation only** — not the durable signal store. **API Gateway + Lambda emit and CLI** are secondary surfaces for **re-emit / debug / backfill** only. Terraform happy path in **`eu-west-1`**. Contract tests always; LLM-as-judge golden set in CI when RAG surfaces change. Research-not-advice. No ranking, paper broker, or non-10-K sources.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: boto3 (Bedrock Converse/InvokeModel, S3, OpenSearch Serverless, Glue), pydantic (models), jsonschema (emission validator), pyarrow/pandas (Parquet signal rows), httpx/requests (EDGAR), typer or argparse (CLI), pytest (+ fixtures), Terraform >= 1.5

**Storage**:
- S3 immutable **raw** lake (EDGAR filings)
- OpenSearch Serverless vector collection (1024-d Titan V2) — **derived RAG index only**
- S3 **curated signals** as Hive-partitioned **Parquet** (`ticker` / `filing_date`) + **AWS Glue Data Catalog** + **Amazon Athena** — **durable signal / analytics warehouse path**
- Optional debug JSON copies under `signals/`; optional CloudWatch Logs

**Testing**: pytest contract/unit/integration; fixture 10-K snippets; LLM-as-judge golden set gated on RAG path changes in CI

**Target Platform**: AWS `eu-west-1` (S3 event → Step Functions / ECS Fargate primary pipeline; Lambda + API Gateway secondary re-emit; OpenSearch Serverless; Bedrock; Glue; Athena)

**Project Type**: Event-driven ingest→index→emit→warehouse pipeline (library + infra) with secondary CLI + HTTP re-emit; not chat-first, not mobile

**Performance Goals**: Demo-scale — when a new 10-K lands, index + emit + warehouse write completes in a single operator session per filing (warm path under ~ few minutes); five-ticker cold backfill via secondary re-emit in one session (target < 15 minutes); index rebuild from lake overnight-acceptable

**Constraints**: AWS-only runtime; hermetic factor catalog only; full EDGAR provenance; validator drops uncited `ok` scores; research-not-advice framing; Terraform-deployable; no ranking/paper-broker/10-Q/8-K/news; durable signals MUST land in warehouse path (not AOSS)

**Scale/Scope**: 5 tickers; latest 10-K/10-K/A each; Phase-1 demo only

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| **I. Hermetic Qualitative Signals** | Closed catalog schema `0.1.0`; five locked factors; `insufficient_evidence` without invented polarity; production emit is on-ingest; CLI/API re-emit only (no chat bypass) | **PASS** — encoded in contracts + data model |
| **II. Auditable Provenance** | EDGAR canonical; immutable S3 raw; rebuildable vectors; required provenance including `filing_date` in JSON **and** chunk metadata **and** warehouse partitions/columns; drop unscored claims | **PASS** — S3 lake + AOSS metadata + Parquet/Glue + validator |
| **III. Phased Scope Discipline** | Phase-1 signal path only; no ranking/paper broker | **PASS** — explicit non-goals |
| **IV. Verifiable Quality Gates** | Contract tests + fixtures mandatory; LLM-as-judge on RAG changes only; not per production request | **PASS** — CI design in research/quickstart |
| **V. Research Signals, Not Advice** | Framing on emissions / secondary API/CLI | **PASS** — contract `disclaimer` / framing field |
| **Tech constraints** | Python; Terraform; AWS deployable | **PASS** — Technical Context |

**Gate evaluation (pre-Phase 0)**: PASS — proceed.

**Gate evaluation (post-Phase 1)**: PASS — design artifacts (`research.md`, `data-model.md`, `contracts/*`, `quickstart.md`) preserve hermeticity, provenance, scope, eval gates, and the locked on-ingest → warehouse durable path. No unjustified complexity violations.

## Project Structure

### Documentation (this feature)

```text
specs/001-10k-signal-demo/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── signal-emission.schema.json
│   ├── signal-warehouse.md          # Durable Parquet/Glue/Athena persist contract
│   ├── batch-emit.openapi.yaml      # Secondary re-emit / backfill HTTP API
│   └── cli-batch-emit.md            # Secondary re-emit / debug / backfill CLI
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/sec_signals/
├── __init__.py
├── models/                 # Pydantic models aligned to contracts
├── edgar/                  # EDGAR resolve, download
├── lake/                   # S3 raw + curated Parquet / optional JSON IO
├── parse/                  # Section-aware chunking
├── retrieve/               # Embed + OpenSearch Serverless (RAG only)
├── extract/                # Bedrock Converse factor extraction
├── validate/               # JSON Schema / provenance gates
├── warehouse/              # Signal → DataFrame → Parquet / Glue path
├── pipeline/               # ingest → index → emit → warehouse (primary on-ingest)
├── api/                    # Lambda HTTP handlers (re-emit / backfill only)
└── cli/                    # Typer/argparse entrypoints (re-emit / debug / backfill)

tests/
├── contract/               # Schema + provenance + warehouse fixtures
├── integration/            # Local stubs / optional AWS
├── unit/
└── golden/                 # LLM-as-judge cases (CI gated)

infra/
├── modules/
│   ├── lake/               # S3 raw + curated; Glue catalog; Athena workgroup
│   ├── vector/             # OpenSearch Serverless
│   ├── compute/            # S3→SFN→Fargate primary; Lambda+API GW secondary
│   └── iam/
└── envs/demo/              # eu-west-1 root module

fixtures/
└── filings/                # Sample 10-K snippets for tests
```

**Structure Decision**: Single Python package (`src/sec_signals`) with Terraform under `infra/`, tests and fixtures at repo root. Primary production path is **S3 object-created → Step Functions → Fargate (index + Haiku emit + warehouse write)**. CLI/API share the same library for **reprocess only**. Matches constitution (Python + Terraform) without a separate frontend.

## Complexity Tracking

> No constitution violations requiring justification. Table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
