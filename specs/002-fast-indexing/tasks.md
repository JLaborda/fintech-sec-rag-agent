---
description: "Task list for fast, observable 10-K indexing (issue #9)"
---

# Tasks: Fast, Observable 10-K Indexing

**Input**: Design documents from `/specs/002-fast-indexing/`

**Prerequisites**: plan.md (required), spec.md (required)

**Tests**: **Strict TDD** — every implementation task begins with a failing test that proves the gap, names the CA it covers, and lists the exact pytest command. CA-5 is **manual / human** (Jorge).

**Organization**: One phase per acceptance criterion (CA-1..CA-5), after minimal setup.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 (fast index + progress), US2 (retries), US3 (packaged schema), or MANUAL
- Include exact file paths and exact pytest commands

## Path Conventions

- Single project: `src/sec_signals/`, `tests/` at repository root

---

## Phase 1: Setup

**Purpose**: Shared retry helper and config knobs used by CA-1..CA-3 (still TDD).

- [ ] T001 [P] **Failing test first (foundation)**: Add `tests/unit/test_retry_backoff.py` asserting `call_with_backoff` retries on a retriable error, respects max attempts **5**, and applies exponential backoff (monkeypatch sleep). Run: `pytest tests/unit/test_retry_backoff.py -k call_with_backoff -v` — expect FAIL. Then implement `src/sec_signals/retrieve/retry.py` until PASS.
- [ ] T002 [P] **Failing test first (foundation)**: Add `tests/unit/test_indexing_settings.py` asserting `Settings` exposes `embed_concurrency` default **8** (env `SEC_SIGNALS_EMBED_CONCURRENCY`) and `opensearch_bulk_size` default **50** (env `SEC_SIGNALS_OPENSEARCH_BULK_SIZE`). Run: `pytest tests/unit/test_indexing_settings.py -k embed_concurrency -v` — expect FAIL. Then extend `src/sec_signals/config.py` until PASS.

**Checkpoint**: Retry helper + settings knobs green.

---

## Phase 2: CA-1 — Concurrent embed + OpenSearch bulk (US1)

**Goal**: `ChunkIndexer.upsert_chunks` embeds concurrently and writes via bulk batches; concurrency configurable.

**Independent Test**: Mocked embedder + search client; assert overlapping embed calls and bulk batch sizes.

- [ ] T003 **CA-1 — Failing test first**: Add `tests/unit/test_indexer_concurrency.py` that:
  - Builds `ChunkIndexer` with `embed_concurrency=4` and a fake embedder that records in-flight concurrency.
  - Asserts peak in-flight embeds &gt; 1 for ≥8 chunks without precomputed embeddings.
  - Asserts fake OpenSearch client receives **bulk** calls (not only per-doc `index`) with batch size ≤ configured `opensearch_bulk_size` (default 50; use small size e.g. 3 in test to force multiple bulks).
  - Run: `pytest tests/unit/test_indexer_concurrency.py -k concurrent_embed_and_bulk -v` — expect FAIL (current `indexer.py` is sequential per-doc `index`).
  - Then implement concurrent `ThreadPoolExecutor` embed + bulk writes in `src/sec_signals/retrieve/indexer.py` (extend `SearchIndexerClient` Protocol with `bulk`) until PASS. Wire defaults from `Settings` where the worker constructs the indexer (`src/sec_signals/pipeline/index.py` / Fargate main) without Terraform changes.

**Checkpoint**: CA-1 unit proof green.

---

## Phase 3: CA-2 — Progress logs `indexed X/Y chunks` (US1)

**Goal**: Indexing emits progress in the exact form `indexed X/Y chunks`.

- [ ] T004 **CA-2 — Failing test first**: Add `tests/unit/test_indexer_progress.py` that captures logger output (or a injectable progress callback if preferred by implementation, but **log text must still appear** as `indexed X/Y chunks`) while upserting N mocked chunks; assert at least one intermediate or final line matches `indexed X/Y chunks` with `Y == N` and a final `indexed N/N chunks`. Run: `pytest tests/unit/test_indexer_progress.py -k indexed_progress -v` — expect FAIL. Then add logging in `src/sec_signals/retrieve/indexer.py` until PASS.

**Checkpoint**: CA-2 unit proof green.

---

## Phase 4: CA-3 — Bedrock & OpenSearch retry with backoff (US2)

**Goal**: Embed and OpenSearch calls retry with exponential backoff and max attempts; mocked unit coverage.

- [ ] T005 [P] **CA-3 — Failing test first (Bedrock)**: Add `tests/unit/test_embed_opensearch_retry.py` case `test_titan_embed_retries_throttling` where fake Bedrock raises throttling twice then succeeds; assert 3 invokes and backoff sleep called; max attempts 5. Run: `pytest tests/unit/test_embed_opensearch_retry.py -k titan_embed_retries_throttling -v` — expect FAIL. Then wrap `TitanEmbedClient.embed` (via `call_with_backoff` in `src/sec_signals/retrieve/titan_embed.py`) until PASS.
- [ ] T006 [P] **CA-3 — Failing test first (OpenSearch)**: In the same file, cases:
  - `test_opensearch_bulk_retries_throttling` — fake bulk transport/HTTP fails with retriable error twice then succeeds; assert retries + max attempts.
  - `test_opensearch_bulk_retries_mixed_item_429` — fake bulk returns HTTP 200 with `errors: true`, most items status 200/201 and **one** item status **429**; assert only the failed item is retried, progress does not count it until success, and unrecovered item failure fails the run.
  - Run: `pytest tests/unit/test_embed_opensearch_retry.py -k "opensearch_bulk_retries_throttling or opensearch_bulk_retries_mixed_item_429" -v` — expect FAIL. Then wrap bulk/index path in `src/sec_signals/retrieve/indexer.py` (inspect `errors` + per-item status after each bulk) until PASS.
- [ ] T007 **CA-3 — Failing test first (exhaustion)**: Case `test_retry_exhausts_after_max_attempts` asserting failure after **5** attempts without infinite loop. Run: `pytest tests/unit/test_embed_opensearch_retry.py -k retry_exhausts_after_max_attempts -v` — expect FAIL then PASS after helper/client behavior matches plan.

**Checkpoint**: CA-3 unit proof green (mocked clients only).

---

## Phase 5: CA-4 — Packaged `signal-emission.schema.json` (US3; closes #8)

**Goal**: Worker loads schema via `importlib.resources` package data; test proves load outside source tree.

- [ ] T008 **CA-4 — Failing test first**: Add `tests/unit/test_emission_schema_packaged.py` that:
  - Invokes `load_emission_schema()` while ensuring the historical path `specs/001-10k-signal-demo/contracts/signal-emission.schema.json` is **not** used (e.g. monkeypatch/chdir/hide path, or assert loader does not open that path).
  - Asserts the packaged `src/sec_signals/schemas/signal-emission.schema.json` is **byte-identical** to `specs/001-10k-signal-demo/contracts/signal-emission.schema.json`.
  - Builds the wheel, installs it into a **fresh virtual environment outside the repository**, runs `load_emission_schema()` from that environment, and asserts the wheel contains `sec_signals/schemas/signal-emission.schema.json` (so the check cannot pass by importing the source-tree copy).
  - Asserts returned schema is a dict with hermetic contract markers (e.g. required properties / `factor_schema_version`).
  - Run: `pytest tests/unit/test_emission_schema_packaged.py -k load_emission_schema_from_package -v` — expect FAIL (current `Path(__file__).parents[3]/specs/...` loader).
  - Then: add `src/sec_signals/schemas/__init__.py` + copy schema to `src/sec_signals/schemas/signal-emission.schema.json`; set `[tool.setuptools.package-data]` in `pyproject.toml`; rewrite `src/sec_signals/validate/emission_validator.py` to `importlib.resources` until PASS.
- [ ] T009 [P] **CA-4 — Regression**: Ensure existing contract tests still pass: `pytest tests/contract/test_signal_emission_schema.py tests/contract/test_provenance_validator.py tests/unit/test_emission_validator.py -v` — fix any path assumptions that still require repo-relative schema only for runtime loader (fixtures may still read the specs contract for comparison).

**Checkpoint**: CA-4 packaging proof green; #8 packaging root cause addressed in library.

---

## Phase 6: CA-5 — Manual verification by Jorge (MANUAL / HUMAN)

**Goal**: One full 10-K indexes in &lt; 5 minutes; SFN `demo-index-emit` reaches `SUCCEEDED`.

> **Type**: Manual / human — **not** an agent-automated CI task. Owner: **Jorge**.

- [ ] T010 **CA-5 — MANUAL (Jorge)**: After CA-1..CA-4 code is merged and a worker image build includes the packaged schema + indexer changes:
  1. Rebuild and push `demo-sec-signals-worker:latest` (or current demo worker tag).
  2. Stop any stuck `demo-index-emit` execution that would retry the old image (optional but recommended per #8).
  3. Re-trigger Step Functions state machine `demo-index-emit` for a sample filing (same or new raw key).
  4. Confirm execution status **`SUCCEEDED`**.
  5. Confirm indexing wall-clock for one full 10-K is **&lt; 5 minutes** (CloudWatch `/sec-signals/demo` timestamps and/or SFN timing).
  6. Confirm logs show `indexed X/Y chunks` and no `FileNotFoundError` for `signal-emission.schema.json`.

**Evidence to record** (paste into issue #9 or PR follow-up comment):

| Evidence field | What to capture |
|----------------|-----------------|
| Worker image digest / tag | ECR image URI + digest pushed |
| SFN execution ARN | `demo-index-emit` execution ARN |
| Terminal status | Must be `SUCCEEDED` |
| Filing identity | bucket/key or CIK + accession |
| Index duration | Start→index-complete (or task runtime) &lt; 5 min |
| Log excerpt | Lines containing `indexed X/Y chunks` and successful emit (no schema traceback) |

**Checkpoint**: CA-5 closed only when Jorge records the evidence above.

---

## Phase 7: Polish

- [ ] T011 [P] Run focused suite for this feature: `pytest tests/unit/test_retry_backoff.py tests/unit/test_indexing_settings.py tests/unit/test_indexer_concurrency.py tests/unit/test_indexer_progress.py tests/unit/test_embed_opensearch_retry.py tests/unit/test_emission_schema_packaged.py -v`
- [ ] T012 Confirm no edits to `src/sec_signals/parse/section_chunker.py` `max_chars`, embedding model locks, or `infra/` Terraform/IAM for this feature.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001/T002 first (shared retry + settings).
- **CA-1 (Phase 2)**: Depends on T002 (concurrency/bulk knobs); T001 helpful before CA-3.
- **CA-2 (Phase 3)**: Depends on CA-1 indexer changes (progress during upsert).
- **CA-3 (Phase 4)**: Depends on T001; can parallelize T005/T006 after helper exists.
- **CA-4 (Phase 5)**: Independent of CA-1..CA-3 files; can start in parallel after Setup if desired.
- **CA-5 (Phase 6)**: Depends on merged implementation + image rebuild; **human only**.
- **Polish**: After CA-1..CA-4 automated work.

### Parallel Opportunities

```bash
# After T001/T002:
# Dev A: T003 → T004 (indexer)
# Dev B: T005/T006/T007 (retries) once T001 done
# Dev C: T008/T009 (schema packaging) — independent files
```

### TDD rule (all automated tasks)

1. Write the failing test named in the task.
2. Run the **exact** pytest command; confirm FAIL for the right reason.
3. Implement the minimal production change.
4. Re-run until PASS.
5. Commit.

---

## Implementation Strategy

### MVP

1. T001–T002 setup.
2. T003 (CA-1) + T004 (CA-2) — demo-visible speed + progress.
3. T005–T007 (CA-3) — throttle safety.
4. T008–T009 (CA-4) — stop schema crash (#8).
5. Hand off T010 (CA-5) to Jorge.

### Notes

- Do not use `Closes` in the docs PR; implementation PR may reference `Refs #9` / close #8 when CA-4 ships per team practice.
- Cost: same Titan tokens; less Fargate time; watch throttling via CA-3 + concurrency knob.
