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
- Vector: OpenSearch Serverless (vector search collection)
- Flow: EDGAR → S3 raw lake → section-aware chunk → Titan embed → AOSS → retrieve top-k → Haiku 4.5 structured extract → schema validate → CLI/API emit
- Tickers: `V`, `MA`, `PYPL`, `XYZ`, `COIN` · forms: `10-K` | `10-K/A` only

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Single project: `src/sec_signals/`, `tests/`, `infra/`, `fixtures/` at repository root (per plan.md)

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and Python package skeleton

- [ ] T001 Create repository layout `src/sec_signals/{models,edgar,lake,parse,retrieve,extract,validate,pipeline,api,cli}/`, `tests/{contract,integration,unit,golden}/`, `fixtures/filings/`, and `infra/{modules/{lake,vector,compute,iam},envs/demo}/` per plan.md
- [ ] T002 Initialize Python 3.12 package with `pyproject.toml` (package `sec_signals`, entrypoint `sec-signals`, deps: boto3, pydantic, jsonschema, httpx, typer, pytest)
- [ ] T003 [P] Add ruff/black (or project-standard) lint/format config in `pyproject.toml` and `.gitignore` entries for `.venv/`, `.env`, Terraform state
- [ ] T004 [P] Add `README` section or `docs/phase1-dev.md` pointing to `specs/001-10k-signal-demo/quickstart.md` and locked Haiku/Titan model IDs

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared models, config, validation, and client stubs required by all stories

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T005 Implement demo universe + enums in `src/sec_signals/models/enums.py` (`DemoTicker` = V|MA|PYPL|XYZ|COIN; `FormType` = 10-K|10-K/A; `FactorId` closed catalog of five; `FactorStatus` = ok|insufficient_evidence)
- [ ] T006 [P] Implement Pydantic models for `Citation`, `FactorSignal` (ok vs insufficient_evidence), `KeyEvent`, `SignalEmission` in `src/sec_signals/models/emission.py` with constraints: `factor_schema_version` const `0.1.0`; `ok.polarity` ∈ [-1.0, 1.0]; `ok.conviction` ∈ [0.0, 1.0]; `insufficient_evidence` forbids `polarity`; exactly five factors
- [ ] T007 [P] Implement `Filing` and `Chunk` models in `src/sec_signals/models/filing.py` requiring `filing_date` (ISO date) on both; Chunk requires `section`, `item`, `chunk_id`, ticker/cik/accession/form
- [ ] T008 Implement schema/provenance validator in `src/sec_signals/validate/emission_validator.py` loading `specs/001-10k-signal-demo/contracts/signal-emission.schema.json`; drop uncited `ok` claims → substitute `insufficient_evidence` with drop reasoning; require research-not-advice `disclaimer`
- [ ] T009 Implement environment config in `src/sec_signals/config.py` for `eu-west-1`, S3 bucket names, AOSS endpoint/collection, Bedrock LLM id `eu.anthropic.claude-haiku-4-5-20251001-v1:0`, embed id `amazon.titan-embed-text-v2:0`, EDGAR User-Agent (from env/SSM — never commit secrets)
- [ ] T010 [P] Implement Bedrock Converse client wrapper for Haiku 4.5 in `src/sec_signals/extract/bedrock_converse.py` (region `eu-west-1`, modelId `eu.anthropic.claude-haiku-4-5-20251001-v1:0`)
- [ ] T011 [P] Implement Titan V2 embed client in `src/sec_signals/retrieve/titan_embed.py` (`amazon.titan-embed-text-v2:0`, dimensions=1024, normalize=true)
- [ ] T012 [P] Implement structured logging helpers in `src/sec_signals/logging_utils.py` (no PII/secrets)

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 - Emit hermetic signals for the demo universe (Priority: P1) 🎯 MVP

**Goal**: Retrieve top-k chunks → Haiku 4.5 structured extraction → validate/drop uncited scores → emit schema `0.1.0` SignalEmission for demo tickers (fixtures or indexed lake).

**Independent Test**: Batch-emit for V,MA,PYPL,XYZ,COIN against fixtures/index; every payload validates against `signal-emission.schema.json`; no invented polarity on `insufficient_evidence`; uncited `ok` scores dropped.

### Tests for User Story 1

> Write these tests FIRST; ensure they FAIL before implementation

- [ ] T013 [P] [US1] Contract tests for hermetic schema + five FactorIds + polarity/conviction ranges in `tests/contract/test_signal_emission_schema.py` using fixtures under `fixtures/filings/` and `specs/001-10k-signal-demo/contracts/signal-emission.schema.json`
- [ ] T014 [P] [US1] Contract tests for `insufficient_evidence` (no polarity) and uncited-ok drop behavior in `tests/contract/test_provenance_validator.py`
- [ ] T015 [P] [US1] Unit tests for factor prompt packing / JSON parse edge cases in `tests/unit/test_extract_parse.py`

### Implementation for User Story 1

- [ ] T016 [P] [US1] Add sample emission fixtures (valid ok, insufficient_evidence, uncited-ok-to-drop) under `fixtures/emissions/` and minimal 10-K text snippets under `fixtures/filings/`
- [ ] T017 [US1] Implement OpenSearch Serverless retrieve (k-NN + metadata filters on `ticker`, `accession_number`, **`filing_date`**) in `src/sec_signals/retrieve/opensearch_client.py`
- [ ] T018 [US1] Implement per-factor top-k retrieval orchestration in `src/sec_signals/retrieve/retriever.py` (semantic query + filters; return Chunks with section/item/quote-capable text)
- [ ] T019 [US1] Implement Haiku 4.5 factor extraction prompts + Converse call producing draft factors/key_events in `src/sec_signals/extract/factor_extractor.py` (modelId MUST be `eu.anthropic.claude-haiku-4-5-20251001-v1:0`; no Sonnet)
- [ ] T020 [US1] Implement emit pipeline `retrieve → extract → validate → persist` in `src/sec_signals/pipeline/emit.py` writing `s3://…/signals/{factor_schema_version}/{ticker}/{accession}/{pipeline_version}.json` via `src/sec_signals/lake/signals.py`
- [ ] T021 [US1] Implement batch emit for ticker list in `src/sec_signals/pipeline/batch_emit.py` (per-ticker errors without inventing scores for other tickers; default latest filing by `filing_date`)
- [ ] T022 [US1] Wire library-level batch emit callable used by later CLI/API in `src/sec_signals/pipeline/__init__.py`

**Checkpoint**: US1 independently testable with fixtures + mocked/local AOSS; hermetic JSON emissions validate

---

## Phase 4: User Story 2 - Ingest and section-aware index latest filings (Priority: P1)

**Goal**: EDGAR latest 10-K/10-K/A → immutable S3 → section-aware parse/chunk (with `filing_date`) → Titan embed → OpenSearch Serverless; index rebuildable from lake.

**Independent Test**: Ingest five tickers; verify immutable raw keys + chunk metadata including `filing_date`; delete AOSS docs and `--rebuild` restores retrieval metadata.

### Tests for User Story 2

- [ ] T023 [P] [US2] Unit tests for section/item chunking and required metadata in `tests/unit/test_parse_chunk.py`
- [ ] T024 [P] [US2] Unit tests for latest 10-K vs 10-K/A selection by `filing_date` in `tests/unit/test_edgar_latest.py`
- [ ] T025 [P] [US2] Integration test (stubbed EDGAR/S3/AOSS) for ingest→index rebuild path in `tests/integration/test_ingest_index.py`

### Implementation for User Story 2

- [ ] T026 [P] [US2] Implement ticker→CIK map and EDGAR latest 10-K/10-K/A resolver (User-Agent compliant) in `src/sec_signals/edgar/client.py` and `src/sec_signals/edgar/universe.py`
- [ ] T027 [US2] Implement immutable raw lake writer `s3://{bucket}/raw/edgar/{cik}/{accession_number}/…` + provenance sidecar (`ticker`,`cik`,`accession_number`,`form`,`filing_date`, source URLs) in `src/sec_signals/lake/raw.py` (never overwrite raw bytes)
- [ ] T028 [US2] Implement section-aware HTML/text parse + chunker (~500–1000 tokens, overlap; offsets when available) in `src/sec_signals/parse/section_chunker.py`
- [ ] T029 [US2] Implement index pipeline: chunk → Titan embed → AOSS upsert with filterable `filing_date` in `src/sec_signals/pipeline/index.py` and `src/sec_signals/retrieve/indexer.py`
- [ ] T030 [US2] Implement rebuild-from-lake (delete derived vectors for accessions, re-embed from S3) in `src/sec_signals/pipeline/reindex.py`
- [ ] T031 [US2] Implement Fargate task entrypoint for parse/chunk/embed/index in `src/sec_signals/pipeline/fargate_index_main.py` (Lambda-friendly ingest fetch may call into `edgar` + `lake` only)

**Checkpoint**: US2 independently testable — lake + AOSS path works; US1 emit can use real indexed filings

---

## Phase 5: User Story 3 - Operate emit via CLI and API (Priority: P2)

**Goal**: Same hermetic contract via `sec-signals` CLI and HTTP batch emit API; research-not-advice framing; no chat UX.

**Independent Test**: Emit same ticker set via CLI and API; schema-valid payloads; identical required fields; disclaimer present.

### Tests for User Story 3

- [ ] T032 [P] [US3] Contract/API shape tests aligned to `specs/001-10k-signal-demo/contracts/batch-emit.openapi.yaml` in `tests/contract/test_batch_emit_api.py`
- [ ] T033 [P] [US3] CLI emit/validate golden-path tests in `tests/integration/test_cli_emit.py`

### Implementation for User Story 3

- [ ] T034 [P] [US3] Implement Typer CLI `emit`, `validate` per `specs/001-10k-signal-demo/contracts/cli-batch-emit.md` in `src/sec_signals/cli/main.py` and `src/sec_signals/cli/emit_cmd.py` (exit codes 0/2/3/4)
- [ ] T035 [P] [US3] Implement CLI `ingest` and `index [--rebuild]` commands in `src/sec_signals/cli/ingest_cmd.py` and `src/sec_signals/cli/index_cmd.py`
- [ ] T036 [US3] Implement Lambda HTTP handlers for `POST /v1/signals:batchEmit` and `GET /v1/health` in `src/sec_signals/api/handlers.py` matching OpenAPI (`BatchEmitRequest.tickers` max 5 unique demo tickers)
- [ ] T037 [US3] Add API auth hook (API key and/or IAM SigV4 configurable) in `src/sec_signals/api/auth.py` — internal demo, not public anonymous
- [ ] T038 [US3] Ensure CLI and API both set `disclaimer` research-not-advice framing and share `pipeline.batch_emit` (no divergent schemas)

**Checkpoint**: US3 independently operable; chat-first surfaces absent

---

## Phase 6: User Story 4 - Deploy happy path and gate quality in CI (Priority: P2)

**Goal**: Terraform-deployable `eu-west-1` happy path (S3, AOSS, Lambda emit, Fargate index, Step Functions, API GW, IAM) + contract CI always + Haiku LLM-as-judge golden set gated on RAG path changes.

**Independent Test**: `terraform apply` (or documented dry-run) yields lake + emit path; `pytest tests/contract` always; `pytest tests/golden -m llm_judge` only when RAG surfaces change.

### Tests for User Story 4

- [ ] T039 [P] [US4] Add LLM-as-judge golden cases + rubric fixtures in `tests/golden/` and `fixtures/golden/` using Haiku 4.5 judge profile `eu.anthropic.claude-haiku-4-5-20251001-v1:0`
- [ ] T040 [P] [US4] Implement judge runner marked `@pytest.mark.llm_judge` in `tests/golden/test_llm_judge.py` (not required on every production emit)

### Implementation for User Story 4

- [ ] T041 [P] [US4] Terraform module for immutable S3 lake + signals prefix in `infra/modules/lake/`
- [ ] T042 [P] [US4] Terraform module for OpenSearch Serverless vector collection (1024-d, metadata mappings including `filing_date`) in `infra/modules/vector/`
- [ ] T043 [P] [US4] Terraform module for Lambda emit API, API Gateway HTTP API, IAM, CloudWatch in `infra/modules/compute/`
- [ ] T044 [US4] Terraform for ECR + Fargate task def + Step Functions ingest/index orchestration in `infra/modules/compute/` (wire with T043)
- [ ] T045 [US4] Demo root module `infra/envs/demo/` for `eu-west-1` with outputs (bucket, AOSS endpoint, API URL, state machine ARN, pipeline version) documented in `specs/001-10k-signal-demo/quickstart.md`
- [ ] T046 [US4] CI workflow `.github/workflows/ci.yml`: always run `pytest tests/contract tests/unit`; run `tests/golden -m llm_judge` only when paths under `src/sec_signals/{retrieve,extract,validate,pipeline}/`, prompts, or factor schema/contracts change
- [ ] T047 [US4] Add path-filter / change-detection notes and env secrets documentation (Bedrock, EDGAR UA) in `docs/phase1-ci.md`

**Checkpoint**: Happy-path deploy + quality gates satisfy US4; constitution eval gates met

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Hardening and validation across stories

- [ ] T048 [P] Align package version / `model_or_pipeline_version` stamping in `src/sec_signals/version.py`
- [ ] T049 [P] Add unit tests for validator edge cases (out-of-range polarity, 10-K/A form, missing filing_date) in `tests/unit/test_validator_edges.py`
- [ ] T050 Explicitly assert non-goals: no ranking/paper-broker/10-Q/8-K/news/chat modules under `src/sec_signals/`; add guard test in `tests/unit/test_scope_guards.py`
- [ ] T051 Run end-to-end validation steps from `specs/001-10k-signal-demo/quickstart.md` and fix gaps
- [ ] T052 [P] Update root `README.md` status to point at Spec Kit plan/tasks and Haiku 4.5 / Titan V2 / AOSS choices (remove stale “stack TBD” where contradicted)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** all user stories
- **User Story 1 (Phase 3)**: After Foundational — MVP emit path (fixtures OK)
- **User Story 2 (Phase 4)**: After Foundational — can parallel with US1; unlocks real EDGAR→index for emit
- **User Story 3 (Phase 5)**: After US1 library emit (T022); prefers US2 for live data but can demo on fixtures
- **User Story 4 (Phase 6)**: After Foundational; Terraform can parallel mid-stories; CI judge needs US1 extract path
- **Polish (Phase 7)**: After desired stories complete

### User Story Dependencies

- **US1 (P1)**: Foundational only — fixture-backed retrieve/extract/validate
- **US2 (P1)**: Foundational only — independently delivers lake+index; feeds US1/US3 for live demo
- **US3 (P2)**: Depends on US1 batch emit library; CLI ingest/index commands depend on US2
- **US4 (P2)**: Infra can start after Foundational; judge golden set depends on US1 extract+validate behavior

### Within Each User Story

- Tests (listed) MUST be written and FAIL before implementation
- Models/config already in Foundational before services
- Retrieve/index before extract/emit where live data is used
- Story complete before treating next priority as done

### Parallel Opportunities

- Phase 1: T003, T004 in parallel after T001–T002
- Phase 2: T006–T007, T010–T012 in parallel after T005
- US1 tests T013–T015 parallel; then implement
- US2 tests T023–T025 parallel; T026 parallel with early US1 work after Foundational
- US3 tests T032–T033 and CLI vs handler files (T034–T035) parallel
- US4 Terraform modules T041–T043 parallel; golden tests T039–T040 parallel

---

## Parallel Example: User Story 1

```bash
# Launch US1 contract/unit tests together:
Task: "Contract tests for hermetic schema in tests/contract/test_signal_emission_schema.py"
Task: "Contract tests for provenance/uncited drop in tests/contract/test_provenance_validator.py"
Task: "Unit tests for extract parse in tests/unit/test_extract_parse.py"

# After tests fail, implement retrieve + extract on different files:
Task: "OpenSearch retrieve client in src/sec_signals/retrieve/opensearch_client.py"
Task: "Haiku 4.5 factor extractor in src/sec_signals/extract/factor_extractor.py"
```

## Parallel Example: User Story 2

```bash
Task: "EDGAR client in src/sec_signals/edgar/client.py"
Task: "Section chunker in src/sec_signals/parse/section_chunker.py"
# Then index pipeline depends on both + Titan embed (Foundational T011)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL)
3. Complete Phase 3: US1 (fixture-backed retrieve → Haiku 4.5 extract → validate → emit)
4. **STOP and VALIDATE** with `pytest tests/contract` + sample batch emit
5. Demo hermetic JSON for at least one ticker

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 → hermetic emit MVP
3. US2 → real EDGAR→S3→Titan→AOSS path; rebuild proof
4. US3 → CLI + API same contract
5. US4 → Terraform happy path + CI contract/judge gates
6. Polish → quickstart validation + scope guards

### Parallel Team Strategy

1. Team completes Setup + Foundational together
2. Then:
   - Dev A: US1 emit/extract/validate
   - Dev B: US2 ingest/index/Fargate entry
   - Dev C: US4 Terraform modules (then CI)
3. US3 integrates A+B surfaces behind shared pipeline

---

## Notes

- [P] tasks = different files, no dependencies on incomplete sibling tasks
- [Story] label maps task to US1–US4 for traceability
- **Never** introduce Claude Sonnet model IDs; generation/judge default is Haiku 4.5 EU geo profile
- Titan V2 embeddings and `filing_date` in AOSS metadata are non-negotiable
- Verify failing tests before implementing listed test tasks
- Commit after each task or logical group
- Stop at checkpoints to validate stories independently
- Out of scope remains: ranking, paper broker, 10-Q/8-K/news, chat-first UX
