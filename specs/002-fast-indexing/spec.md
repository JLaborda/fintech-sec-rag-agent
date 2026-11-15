# Feature Specification: Fast, Observable 10-K Indexing

**Feature Branch**: `002-fast-indexing`

**Created**: 2026-11-15

**Status**: Draft

**Input**: GitHub issue #9 — index 1–2 full 10-K filings end to end in reasonable time for interview demos; concurrent/batched embeddings + OpenSearch writes; progress logs; retries; package emission schema so the Fargate worker no longer crashes (absorbs #8). Spec Kit path: short.

**Related**: Issue #8 diagnosis (missing `signal-emission.schema.json` in worker image; sequential embed+index ~15 min per filing) informs CA-4 and performance baseline only.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Index a full 10-K quickly with progress (Priority: P1)

A demo operator needs a full 10-K filing indexed (embed + vector upsert) fast enough for an interview session, with clear progress so they can see the job advancing instead of waiting ~15 minutes of silent sequential work.

**Why this priority**: Without faster, observable indexing, the RAG demo cannot be shown reliably in interview timeboxes.

**Independent Test**: Run indexing over a representative chunk list with mocked Bedrock/OpenSearch clients and confirm concurrent embedding, batched upserts, and progress lines of the form `indexed X/Y chunks`.

**Acceptance Scenarios**:

1. **Given** a filing that yields many chunks, **When** `upsert_chunks` runs, **Then** chunks are embedded concurrently (not strictly one-at-a-time) and written to the vector index in batches, and concurrency is configurable.
2. **Given** indexing is in progress, **When** chunks complete, **Then** logs include progress messages matching `indexed X/Y chunks` until X equals Y.
3. **Given** a full sample 10-K in the demo pipeline, **When** indexing completes under load comparable to today, **Then** one full 10-K indexes in under 5 minutes (operator-verified on the live worker path).

---

### User Story 2 - Survive transient Bedrock and OpenSearch failures (Priority: P1)

A platform operator needs indexing to tolerate throttling and transient errors from embedding and vector-store APIs so a single blip does not waste a long Fargate run.

**Why this priority**: Concurrent calls increase throttling risk; without bounded retries the speedup is fragile.

**Independent Test**: Unit tests with mocked clients that fail a fixed number of times then succeed; assert exponential backoff and a hard maximum attempt count.

**Acceptance Scenarios**:

1. **Given** Bedrock embed returns a throttling or transient error, **When** embedding a chunk, **Then** the call retries with exponential backoff up to a configured maximum number of attempts before failing.
2. **Given** OpenSearch bulk/index returns a throttling or transient error, **When** writing a batch, **Then** the call retries with exponential backoff up to a configured maximum number of attempts before failing.
3. **Given** unit tests with mocked clients, **When** the suite runs, **Then** retry/backoff behavior for both Bedrock and OpenSearch is covered without live AWS calls.

---

### User Story 3 - Load emission schema from packaged resources (Priority: P1)

A Fargate worker must validate hermetic emissions after indexing without depending on a repo-tree path under `specs/` that is absent from the installed package image (root cause from #8).

**Why this priority**: Today indexing may finish then the worker crashes on missing schema, so the Step Functions execution never reaches success.

**Independent Test**: A test loads the schema via the production loader while the process working directory and filesystem do not expose the repo `specs/` tree, proving package resource data works outside the source tree.

**Acceptance Scenarios**:

1. **Given** the `sec_signals` package is installed as it is in the worker image, **When** the emission validator loads `signal-emission.schema.json`, **Then** it loads successfully as packaged resource data (not a path relative to the repository tree).
2. **Given** a test that does not have the repo `specs/` tree available beside the installed package, **When** `load_emission_schema` runs, **Then** it still returns a valid schema document (closes the packaging failure described in #8).

---

### Edge Cases

- Empty chunk list: indexing returns zero and may log `indexed 0/0 chunks` or skip progress without error.
- Concurrency set to 1: behavior remains correct (sequential embedding) with batched writes still applied when batch size > 1.
- Last partial OpenSearch batch: remaining documents still flush.
- Exhausted retries: failure is raised after the maximum attempts; no infinite loop.
- Pre-embedded chunks: existing embeddings are reused; concurrency applies only to chunks that still need embedding.
- Schema file missing from package build: tests fail in CI; worker must not silently fall back to a repo-relative path.

## Requirements *(mandatory)*

### Functional Requirements

Mapped to issue acceptance criteria CA-1..CA-5.

- **FR-001 (CA-1)**: `upsert_chunks` in the chunk indexer MUST embed chunks concurrently and write to OpenSearch in bulk batches; concurrency MUST be configurable via a documented configuration knob.
- **FR-002 (CA-2)**: Indexing MUST log progress in the exact form `indexed X/Y chunks` (where X is completed count and Y is total chunks for the run).
- **FR-003 (CA-3)**: Bedrock embedding calls and OpenSearch write calls MUST retry with exponential backoff and a maximum number of attempts (including throttling); this behavior MUST be covered by unit tests with mocked clients.
- **FR-004 (CA-4)**: The worker/validator MUST load `signal-emission.schema.json` as packaged package resource data (not a path relative to the repository tree); a test MUST prove it loads outside the source tree. This absorbs and closes the packaging defect in #8.
- **FR-005 (CA-5)**: One full 10-K MUST index in under 5 minutes on the demo path, and Step Functions execution `demo-index-emit` MUST reach `SUCCEEDED` after the fixed worker image is deployed (manual verification by Jorge).

### Key Entities

- **Chunk**: Existing filing text segment with metadata and optional embedding; unchanged shape for this feature.
- **Index progress**: Pair `(X, Y)` reported in logs as chunks complete.
- **Emission schema**: Versioned JSON Schema for hermetic signal payloads; must travel with the installable package.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Operators can index one full demo 10-K in under 5 minutes wall-clock on the demo worker path (vs ~15 minutes sequential baseline from #8 diagnosis).
- **SC-002**: During indexing, progress is observable as successive `indexed X/Y chunks` log lines ending at `indexed Y/Y chunks`.
- **SC-003**: Transient embedding and vector-store failures that succeed within the retry budget do not fail the indexing run.
- **SC-004**: After packaging fix, emission validation succeeds in an environment without the repository `specs/` tree (no schema `FileNotFoundError`).
- **SC-005**: Demo Step Functions run `demo-index-emit` reaches `SUCCEEDED` for a sample filing once the rebuilt worker is in place.

## Out of scope

Copied in meaning from issue #9:

- No Terraform, IAM, or any other AWS infrastructure changes.
- Issues #4, #5, and #6 remain out of scope for this feature.
- No change to chunking `max_chars` in `section_chunker.py`.
- No change to the embedding model (Titan Text Embeddings V2 remains locked).

## Assumptions

- Baseline problem is sequential per-chunk embed + per-chunk index (~15 min per 10-K) plus post-index schema crash (#8), not hanging pull/ENI/IAM.
- Titan embedding cost is billed per input token, not per API call; raising concurrency should not increase token spend for the same corpus, and shorter Fargate runtime should not raise compute cost (watch throttling; handled by retries).
- Demo verification of CA-5 (rebuild/push worker image, re-trigger SFN) is performed by Jorge; implementers deliver code + automated tests for CA-1..CA-4.
- Existing hermetic factor contract, provenance rules, and research-not-advice framing are unchanged; this feature only speeds and hardens indexing/packaging on the existing Phase-1 path.
- Constitution Phase-1 surfaces (RAG → hermetic signals) remain in force; no ranking or paper-broker work.
