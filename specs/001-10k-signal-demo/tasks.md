---
description: "Task list for phase-1 SEC 10-K qualitative signal generator"
---

# Tasks: Phase-1 SEC 10-K Qualitative Signal Generator

**Input**: Design documents from `/specs/001-10k-signal-demo/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Included — spec/constitution mandate contract tests + fixtures always, and LLM-as-judge golden set when RAG surfaces change (FR-021, FR-022, User Story 4).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

**Locked stack (do not drift)**:
- Region: `eu-west-1`
- LLM: Bedrock Converse Claude **Haiku 4.5** — runtime `modelId` `eu.anthropic.claude-haiku-4-5-20251001-v1:0` (not Sonnet)
- Embeddings: Titan Text Embeddings V2 — `amazon.titan-embed-text-v2:0` @ 1024-d
- Vector: OpenSearch Serverless (vector search collection) — **RAG retrieval only**, not durable signals
- Durable signals: **S3 curated Parquet** partitioned by `ticker` / `filing_date` + **Glue Data Catalog** + **Athena**
- **Primary flow**: EDGAR → S3 raw → **S3 event → Step Functions → Fargate** (section-aware chunk → Titan embed → AOSS → retrieve → Haiku 4.5 extract → validate → **warehouse Parquet write**)
- **Secondary flow**: CLI + API Gateway/Lambda **re-emit / debug / backfill only** (same library + warehouse writer)
- Tickers: `V`, `MA`, `PYPL`, `XYZ`, `COIN` · forms: `10-K` | `10-K/A` only

**Task ID policy**: IDs T001–T052 retained for stability; descriptions updated in place for the locked architecture. New work uses T053+. Tasks that no longer match the primary path are marked **OBSOLETE** or **DEMOTED** in the description (checkbox left unchecked — do not implement obsolete behavior).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Single project: `src/sec_signals/`, `tests/`, `infra/`, `fixtures/` at repository root (per plan.md)

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and Python package skeleton

- [X] T001 Create repository layout `src/sec_signals/{models,edgar,lake,parse,retrieve,extract,validate,warehouse,pipeline,api,cli}/`, `tests/{contract,integration,unit,golden}/`, `fixtures/filings/`, and `infra/{modules/{lake,vector,compute,iam},envs/demo}/` per plan.md
- [X] T002 Initialize Python 3.12 package with `pyproject.toml` (package `sec_signals`, entrypoint `sec-signals`, deps: boto3, pydantic, jsonschema, httpx, typer, pyarrow, pandas, pytest)
- [X] T003 [P] Add ruff/black (or project-standard) lint/format config in `pyproject.toml` and `.gitignore` entries for `.venv/`, `.env`, Terraform state
- [X] T004 [P] Add `README` section or `docs/phase1-dev.md` pointing to `specs/001-10k-signal-demo/quickstart.md` and locked Haiku/Titan/AOSS/Parquet+Glue+Athena choices

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared models, config, validation, and client stubs required by all stories

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 Implement demo universe + enums in `src/sec_signals/models/enums.py` (`DemoTicker` = V|MA|PYPL|XYZ|COIN; `FormType` = 10-K|10-K/A; `FactorId` closed catalog of five; `FactorStatus` = ok|insufficient_evidence)
- [X] T006 [P] Implement Pydantic models for `Citation`, `FactorSignal` (ok vs insufficient_evidence), `KeyEvent`, `SignalEmission` in `src/sec_signals/models/emission.py` with constraints: `factor_schema_version` const `0.1.0`; `ok.polarity` ∈ [-1.0, 1.0]; `ok.conviction` ∈ [0.0, 1.0]; `insufficient_evidence` forbids `polarity`; exactly five factors
- [X] T007 [P] Implement `Filing` and `Chunk` models in `src/sec_signals/models/filing.py` requiring `filing_date` (ISO date) on both; Chunk requires `section`, `item`, `chunk_id`, ticker/cik/accession/form
- [X] T008 Implement schema/provenance validator in `src/sec_signals/validate/emission_validator.py` loading `specs/001-10k-signal-demo/contracts/signal-emission.schema.json`; drop uncited `ok` claims → substitute `insufficient_evidence` with drop reasoning; require research-not-advice `disclaimer`
- [X] T009 Implement environment config in `src/sec_signals/config.py` for `eu-west-1`, S3 raw + curated prefixes, Glue DB/table, Athena workgroup, AOSS endpoint/collection, Bedrock LLM id `eu.anthropic.claude-haiku-4-5-20251001-v1:0`, embed id `amazon.titan-embed-text-v2:0`, EDGAR User-Agent (from env/SSM — never commit secrets)
- [X] T010 [P] Implement Bedrock Converse client wrapper for Haiku 4.5 in `src/sec_signals/extract/bedrock_converse.py` (region `eu-west-1`, modelId `eu.anthropic.claude-haiku-4-5-20251001-v1:0`)
- [X] T011 [P] Implement Titan V2 embed client in `src/sec_signals/retrieve/titan_embed.py` (`amazon.titan-embed-text-v2:0`, dimensions=1024, normalize=true)
- [X] T012 [P] Implement structured logging helpers in `src/sec_signals/logging_utils.py` (no PII/secrets)
- [X] T053 [P] Implement `SignalFactorRow` model + emission→rows flatten helpers in `src/sec_signals/models/warehouse.py` matching `data-model.md` (five rows; `polarity` null when `insufficient_evidence`; partition fields `ticker`, `filing_date`)

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 - Hermetic extract / validate / warehouse library (Priority: P1) 🎯 MVP

**Goal**: Library path: retrieve top-k → Haiku 4.5 structured extraction → validate/drop uncited scores → produce schema `0.1.0` SignalEmission and **durable SignalFactorRow Parquet writes**. Used by primary on-ingest Fargate and by secondary re-emit.

**Independent Test**: Batch library emit for V,MA,PYPL,XYZ,COIN against fixtures/index; every payload validates against `signal-emission.schema.json`; warehouse flatten yields five rows/filing; no invented polarity on `insufficient_evidence`; uncited `ok` scores dropped.

### Tests for User Story 1

> Write these tests FIRST; ensure they FAIL before implementation

- [X] T013 [P] [US1] Contract tests for hermetic schema + five FactorIds + polarity/conviction ranges in `tests/contract/test_signal_emission_schema.py` using fixtures under `fixtures/filings/` and `specs/001-10k-signal-demo/contracts/signal-emission.schema.json`
- [X] T014 [P] [US1] Contract tests for `insufficient_evidence` (no polarity) and uncited-ok drop behavior in `tests/contract/test_provenance_validator.py`
- [X] T015 [P] [US1] Unit tests for factor prompt packing / JSON parse edge cases in `tests/unit/test_extract_parse.py`
- [X] T057 [P] [US1] Contract tests for warehouse row shape + Hive partitions (`ticker`, `filing_date`) per `specs/001-10k-signal-demo/contracts/signal-warehouse.md` in `tests/contract/test_signal_warehouse.py`

### Implementation for User Story 1

- [X] T016 [P] [US1] Add sample emission fixtures (valid ok, insufficient_evidence, uncited-ok-to-drop) under `fixtures/emissions/` and minimal 10-K text snippets under `fixtures/filings/`
- [X] T017 [US1] Implement OpenSearch Serverless retrieve (k-NN + metadata filters on `ticker`, `accession_number`, **`filing_date`**) in `src/sec_signals/retrieve/opensearch_client.py` (RAG only)
- [X] T018 [US1] Implement per-factor top-k retrieval orchestration in `src/sec_signals/retrieve/retriever.py` (semantic query + filters; return Chunks with section/item/quote-capable text)
- [X] T019 [US1] Implement Haiku 4.5 factor extraction prompts + Converse call producing draft factors/key_events in `src/sec_signals/extract/factor_extractor.py` (modelId MUST be `eu.anthropic.claude-haiku-4-5-20251001-v1:0`; no Sonnet)
- [X] T020 [US1] Implement emit pipeline `retrieve → extract → validate → warehouse persist` in `src/sec_signals/pipeline/emit.py` writing curated Parquet via `src/sec_signals/warehouse/parquet_writer.py` per `contracts/signal-warehouse.md`; optional debug JSON via `src/sec_signals/lake/signals.py` under `s3://…/signals/…` (**not** the durable store)
- [X] T054 [US1] Implement Parquet warehouse writer (Hive partitions `factor_schema_version`/`ticker`/`filing_date`, five `SignalFactorRow`s) in `src/sec_signals/warehouse/parquet_writer.py`
- [X] T021 [US1] Implement batch emit for ticker list in `src/sec_signals/pipeline/batch_emit.py` (per-ticker errors without inventing scores for other tickers; default latest filing by `filing_date`; shared by secondary CLI/API and backfill)
- [X] T022 [US1] Wire library-level emit / batch_emit callables used by Fargate primary path and secondary CLI/API in `src/sec_signals/pipeline/__init__.py`

**Checkpoint**: US1 independently testable with fixtures + mocked/local AOSS; hermetic JSON + curated Parquet rows validate

---

## Phase 4: User Story 2 - Primary on-ingest index + emit + warehouse (Priority: P1)

**Goal**: EDGAR latest 10-K/10-K/A → immutable S3; **on raw object create**, Fargate (via Step Functions): section-aware parse/chunk (with `filing_date`) → Titan embed → AOSS → **immediate Haiku emit** → curated Parquet warehouse. Index rebuildable from lake. AOSS is RAG-only.

**Independent Test**: Ingest five tickers; verify immutable raw keys; pipeline auto-runs index+emit+warehouse; chunk metadata includes `filing_date`; Athena/Glue sees five factor rows; delete AOSS docs and `--rebuild` restores retrieval metadata without treating AOSS as signal store.

### Tests for User Story 2

- [ ] T023 [P] [US2] Unit tests for section/item chunking and required metadata in `tests/unit/test_parse_chunk.py`
- [ ] T024 [P] [US2] Unit tests for latest 10-K vs 10-K/A selection by `filing_date` in `tests/unit/test_edgar_latest.py`
- [ ] T025 [P] [US2] Integration test (stubbed EDGAR/S3/AOSS/warehouse) for ingest→index→emit→warehouse path in `tests/integration/test_ingest_index_emit.py` (rename/replace prior ingest-only focus of `test_ingest_index.py`)

### Implementation for User Story 2

- [ ] T026 [P] [US2] Implement ticker→CIK map and EDGAR latest 10-K/10-K/A resolver (User-Agent compliant) in `src/sec_signals/edgar/client.py` and `src/sec_signals/edgar/universe.py`
- [ ] T027 [US2] Implement immutable raw lake writer `s3://{bucket}/raw/edgar/{cik}/{accession_number}/…` + provenance sidecar (`ticker`,`cik`,`accession_number`,`form`,`filing_date`, source URLs) in `src/sec_signals/lake/raw.py` (never overwrite raw bytes)
- [ ] T028 [US2] Implement section-aware HTML/text parse + chunker (~500–1000 tokens, overlap; offsets when available) in `src/sec_signals/parse/section_chunker.py`
- [ ] T029 [US2] Implement index pipeline: chunk → Titan embed → AOSS upsert with filterable `filing_date` in `src/sec_signals/pipeline/index.py` and `src/sec_signals/retrieve/indexer.py`
- [ ] T030 [US2] Implement rebuild-from-lake (delete derived vectors for accessions, re-embed from S3) in `src/sec_signals/pipeline/reindex.py`
- [ ] T031 [US2] Implement Fargate task entrypoint for **primary** `parse/chunk/embed/index → emit → warehouse` in `src/sec_signals/pipeline/fargate_index_emit_main.py` (replace prior index-only `fargate_index_main.py` naming); modes: `index_emit` (default on S3 event), `index_only`/`rebuild` for ops
- [ ] T055 [US2] Implement S3 object-created → Step Functions trigger wiring (raw prefix filter for 10-K/10-K/A) documented/coded for `infra` + handler stub in `src/sec_signals/pipeline/s3_event.py` so new raw filings start primary Fargate `index_emit`

**Checkpoint**: US2 independently testable — lake + AOSS RAG + on-ingest warehouse signals; primary path no longer depends on HTTP emit

---

## Phase 5: User Story 3 - Secondary re-emit via CLI and API (Priority: P2)

**Goal**: Same hermetic contract via `sec-signals` CLI and HTTP batch re-emit API for **debug / backfill / reprocess only**; research-not-advice framing; no chat UX. **Not** the primary production path.

**Independent Test**: Re-emit same ticker set via CLI and API; schema-valid payloads; warehouse rows written; identical required fields; disclaimer present; docs/CLI help state secondary role.

### Tests for User Story 3

- [ ] T032 [P] [US3] Contract/API shape tests aligned to `specs/001-10k-signal-demo/contracts/batch-emit.openapi.yaml` (secondary re-emit) in `tests/contract/test_batch_emit_api.py`
- [ ] T033 [P] [US3] CLI emit/validate golden-path tests in `tests/integration/test_cli_emit.py` asserting warehouse persist default and secondary/backfill framing in help text

### Implementation for User Story 3

- [ ] T034 [P] [US3] Implement Typer CLI `emit`, `validate` per `specs/001-10k-signal-demo/contracts/cli-batch-emit.md` in `src/sec_signals/cli/main.py` and `src/sec_signals/cli/emit_cmd.py` (exit codes 0/2/3/4; emit documented as re-emit/backfill)
- [ ] T035 [P] [US3] Implement CLI `ingest` and `index [--rebuild]` commands in `src/sec_signals/cli/ingest_cmd.py` and `src/sec_signals/cli/index_cmd.py` (`ingest` lands raw objects that trigger primary path; `index` is ops rebuild helper)
- [ ] T036 [US3] **DEMOTED (reprocess only)**: Implement Lambda HTTP handlers for `POST /v1/signals:batchEmit` and `GET /v1/health` in `src/sec_signals/api/handlers.py` matching OpenAPI — **secondary re-emit/backfill**, not primary production emit; include optional `warehouse_uri` in results
- [ ] T037 [US3] Add API auth hook (API key and/or IAM SigV4 configurable) in `src/sec_signals/api/auth.py` — internal demo, not public anonymous
- [ ] T038 [US3] Ensure CLI and API both set `disclaimer` research-not-advice framing and share `pipeline.batch_emit` + warehouse writer with Fargate primary path (no divergent schemas)

**OBSOLETE (do not implement)**: Treating API Gateway + Lambda batch emit as the sole/primary production signal path (superseded by S3→Fargate on-ingest). Prior wording of T036 as primary emit is void.

**Checkpoint**: US3 independently operable as reprocess surface; chat-first surfaces absent; primary path remains event-driven

---

## Phase 6: User Story 4 - Deploy happy path and gate quality in CI (Priority: P2)

**Goal**: Terraform-deployable `eu-west-1` happy path (S3 raw+curated, Glue, Athena, AOSS, **S3→Step Functions→Fargate primary**, secondary Lambda re-emit + API GW, IAM) + contract CI always + Haiku LLM-as-judge golden set gated on RAG path changes.

**Independent Test**: `terraform apply` (or documented dry-run) yields lake + primary on-ingest path + warehouse; `pytest tests/contract` always; `pytest tests/golden -m llm_judge` only when RAG surfaces change.

### Tests for User Story 4

- [ ] T039 [P] [US4] Add LLM-as-judge golden cases + rubric fixtures in `tests/golden/` and `fixtures/golden/` using Haiku 4.5 judge profile `eu.anthropic.claude-haiku-4-5-20251001-v1:0`
- [ ] T040 [P] [US4] Implement judge runner marked `@pytest.mark.llm_judge` in `tests/golden/test_llm_judge.py` (not required on every production emit, including on-ingest)

### Implementation for User Story 4

- [ ] T041 [P] [US4] Terraform module for immutable S3 raw lake + curated signals prefix in `infra/modules/lake/`
- [ ] T056 [P] [US4] Terraform for Glue database/table `curated_signals` (partitions `factor_schema_version`,`ticker`,`filing_date`) + Athena workgroup in `infra/modules/lake/` (or `infra/modules/warehouse/`) per `contracts/signal-warehouse.md`
- [ ] T042 [P] [US4] Terraform module for OpenSearch Serverless vector collection (1024-d, metadata mappings including `filing_date`) in `infra/modules/vector/` — RAG only
- [ ] T043 [P] [US4] **DEMOTED compute surface**: Terraform for secondary Lambda re-emit API, API Gateway HTTP API, IAM, CloudWatch in `infra/modules/compute/` (not primary emit)
- [ ] T044 [US4] Terraform for ECR + Fargate task def + Step Functions **primary** ingest/index/emit/warehouse orchestration + S3 event notifications on raw prefix in `infra/modules/compute/` (wire with T043 secondary API)
- [ ] T045 [US4] Demo root module `infra/envs/demo/` for `eu-west-1` with outputs (bucket, curated prefix, Glue/Athena, AOSS endpoint, state machine ARN, secondary API URL, pipeline version) documented in `specs/001-10k-signal-demo/quickstart.md`
- [ ] T046 [US4] CI workflow `.github/workflows/ci.yml`: always run `pytest tests/contract tests/unit`; run `tests/golden -m llm_judge` only when paths under `src/sec_signals/{retrieve,extract,validate,warehouse,pipeline}/`, prompts, or factor schema/contracts change
- [ ] T047 [US4] Add path-filter / change-detection notes and env secrets documentation (Bedrock, EDGAR UA) in `docs/phase1-ci.md`

**Checkpoint**: Happy-path deploy + quality gates satisfy US4; constitution eval gates met; warehouse is durable signal store

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Hardening and validation across stories

- [ ] T048 [P] Align package version / `model_or_pipeline_version` stamping in `src/sec_signals/version.py`
- [ ] T049 [P] Add unit tests for validator edge cases (out-of-range polarity, 10-K/A form, missing filing_date) in `tests/unit/test_validator_edges.py`
- [ ] T050 Explicitly assert non-goals: no ranking/paper-broker/10-Q/8-K/news/chat modules under `src/sec_signals/`; assert durable signals are not AOSS-only; add guard test in `tests/unit/test_scope_guards.py`
- [ ] T051 Run end-to-end validation steps from `specs/001-10k-signal-demo/quickstart.md` (on-ingest primary + secondary re-emit) and fix gaps
- [ ] T052 [P] Update root `README.md` status to point at Spec Kit plan/tasks and Haiku 4.5 / Titan V2 / AOSS (RAG) / Parquet+Glue+Athena choices (remove stale “stack TBD” / primary-HTTP-emit wording where contradicted)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** all user stories (includes T053 warehouse model)
- **User Story 1 (Phase 3)**: After Foundational — MVP extract/validate/**warehouse library** (fixtures OK)
- **User Story 2 (Phase 4)**: After Foundational; needs US1 emit library (T020/T022/T054) for on-ingest emit — **primary production path**
- **User Story 3 (Phase 5)**: After US1 library emit (T022); prefers US2 for live data; **secondary reprocess only**
- **User Story 4 (Phase 6)**: After Foundational; Terraform can parallel mid-stories; primary SFN/Fargate + Glue needs US2 design; CI judge needs US1 extract path
- **Polish (Phase 7)**: After desired stories complete

### User Story Dependencies

- **US1 (P1)**: Foundational — fixture-backed retrieve/extract/validate/warehouse
- **US2 (P1)**: Foundational + US1 emit/warehouse library — delivers primary S3→Fargate index+emit+warehouse
- **US3 (P2)**: Depends on US1 batch emit library; CLI ingest depends on US2 lake writer; **demoted** from primary emit surface
- **US4 (P2)**: Infra can start after Foundational; judge golden set depends on US1 extract+validate behavior

### Phase shifts vs prior tasks.md (summary)

| Item | Prior | Now |
|------|-------|-----|
| Primary emit | US3 Lambda/CLI (Phase 5) + US1 library | **US2 on-ingest Fargate** (Phase 4) using US1 library |
| US3 Lambda/CLI (T036 etc.) | Primary operator surface | **DEMOTED** re-emit/backfill |
| Durable store | S3 JSON `signals/` (+ AOSS confusion risk) | **Curated Parquet + Glue/Athena**; AOSS = RAG only |
| New tasks | — | T053–T057 (warehouse model/writer/tests, S3→SFN, Glue/Athena TF) |
| T031 | Index-only Fargate | **Index + emit + warehouse** Fargate entry |
| T020 | Persist JSON under `signals/` | **Warehouse Parquet** (+ optional debug JSON) |
| T025 / T044 / T041–T045 | Index/API-centric | On-ingest + warehouse-centric |

### Within Each User Story

- Tests (listed) MUST be written and FAIL before implementation
- Models/config already in Foundational before services
- Retrieve/index before extract/emit where live data is used
- Story complete before treating next priority as done

### Parallel Opportunities

- Phase 1: T003, T004 in parallel after T001–T002
- Phase 2: T006–T007, T010–T012, T053 in parallel after T005
- US1 tests T013–T015, T057 parallel; then implement
- US2 tests T023–T025 parallel; T026 parallel with early US1 work after Foundational
- US3 tests T032–T033 and CLI vs handler files (T034–T035) parallel
- US4 Terraform modules T041–T043, T056 parallel; golden tests T039–T040 parallel

---

## Parallel Example: User Story 1

```bash
# Launch US1 contract/unit tests together:
Task: "Contract tests for hermetic schema in tests/contract/test_signal_emission_schema.py"
Task: "Contract tests for provenance/uncited drop in tests/contract/test_provenance_validator.py"
Task: "Contract tests for warehouse rows in tests/contract/test_signal_warehouse.py"
Task: "Unit tests for extract parse in tests/unit/test_extract_parse.py"

# After tests fail, implement retrieve + extract + warehouse on different files:
Task: "OpenSearch retrieve client in src/sec_signals/retrieve/opensearch_client.py"
Task: "Haiku 4.5 factor extractor in src/sec_signals/extract/factor_extractor.py"
Task: "Parquet warehouse writer in src/sec_signals/warehouse/parquet_writer.py"
```

## Parallel Example: User Story 2

```bash
Task: "EDGAR client in src/sec_signals/edgar/client.py"
Task: "Section chunker in src/sec_signals/parse/section_chunker.py"
# Then index+emit Fargate depends on both + Titan embed (T011) + US1 emit library
Task: "S3 event → Step Functions wiring in src/sec_signals/pipeline/s3_event.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Library)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL, includes warehouse model)
3. Complete Phase 3: US1 (fixture-backed retrieve → Haiku 4.5 extract → validate → **Parquet warehouse**)
4. **STOP and VALIDATE** with `pytest tests/contract` + sample library emit
5. Demo hermetic JSON + five warehouse rows for at least one ticker

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 → hermetic emit + warehouse library MVP
3. US2 → **primary** EDGAR→S3→event→Fargate index+emit+warehouse; AOSS rebuild proof
4. US3 → **secondary** CLI + API re-emit same contract
5. US4 → Terraform happy path (Glue/Athena + SFN) + CI contract/judge gates
6. Polish → quickstart validation + scope guards

### Parallel Team Strategy

1. Team completes Setup + Foundational together
2. Then:
   - Dev A: US1 extract/validate/warehouse
   - Dev B: US2 ingest/index/Fargate on-ingest + S3 events
   - Dev C: US4 Terraform modules (then CI)
3. US3 integrates A surfaces as secondary reprocess behind shared pipeline

---

## Notes

- [P] tasks = different files, no dependencies on incomplete sibling tasks
- [Story] label maps task to US1–US4 for traceability
- **Never** introduce Claude Sonnet model IDs; generation/judge default is Haiku 4.5 EU geo profile
- Titan V2 embeddings and `filing_date` in AOSS metadata are non-negotiable
- Durable signals MUST land in curated Parquet / Glue / Athena — **not** AOSS
- API/CLI emit is reprocess only — do not re-center the design on Lambda as primary
- Verify failing tests before implementing listed test tasks
- Commit after each task or logical group
- Stop at checkpoints to validate stories independently
- Out of scope remains: ranking, paper broker, 10-Q/8-K/news, chat-first UX
