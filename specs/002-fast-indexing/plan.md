# Implementation Plan: Fast, Observable 10-K Indexing

**Branch**: `002-fast-indexing` | **Date**: 2026-11-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-fast-indexing/spec.md` (issue #9; #8 diagnosis for packaging root cause and ~15 min baseline)

**Note**: Spec Kit **short** path — this plan is the technical design artifact; no separate `research.md` / `data-model.md` / new contracts for this feature.

## Summary

Speed up and harden Phase-1 Fargate indexing so one full 10-K finishes in under 5 minutes with visible progress, and fix emission-schema packaging so the worker validates without a repo-relative `specs/` path. Approach: thread-pool concurrent Titan embeds with a config knob, OpenSearch `_bulk` batching, shared exponential backoff with max attempts for Bedrock and OpenSearch (incl. throttling), progress logs `indexed X/Y chunks`, and ship `signal-emission.schema.json` as package resource data via `importlib.resources` + setuptools package data.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Existing — boto3 (Bedrock Runtime Titan embed, OpenSearch Serverless), pydantic, jsonschema, pytest. Stdlib: `concurrent.futures`, `importlib.resources`, logging.

**Storage**: Unchanged — S3 raw lake; OpenSearch Serverless derived vector index; curated Parquet warehouse (emit path unchanged except schema load).

**Testing**: pytest unit tests with mocked Bedrock/OpenSearch clients; packaging test that loads schema without repo `specs/` tree. No live AWS required for CA-1..CA-4.

**Target Platform**: Existing demo Fargate worker / SFN `demo-index-emit` in `eu-west-1` (no infra PR in this feature).

**Project Type**: Library change inside `sec_signals` (indexer, embed client retry, validator packaging, `pyproject.toml` package data).

**Performance Goals**: One full 10-K index wall-clock **&lt; 5 minutes** (CA-5); progress observable throughout.

**Constraints**: No Terraform/IAM/AWS infra changes; no #4/#5/#6; do not change `section_chunker.max_chars` or embedding model id/dimensions; keep hermetic schema content identical (packaging only).

**Scale/Scope**: Demo filings (1–2 full 10-Ks); concurrency tuned for Bedrock throttle risk, not multi-tenant scale-out.

## Constitution Check

*GATE: Must pass before implementation.*

| Principle | Gate | Status |
|-----------|------|--------|
| **I. Hermetic Qualitative Signals** | Schema bytes unchanged; loader only moves to package resources | **PASS** |
| **II. Auditable Provenance** | Chunk metadata / upsert body fields unchanged | **PASS** |
| **III. Phased Scope Discipline** | Indexing/packaging only; no ranking/paper broker; no new forms | **PASS** |
| **IV. Verifiable Quality Gates** | Unit tests for concurrency/batch/retry/progress; packaging load test; CA-5 manual | **PASS** |
| **V. Research Signals, Not Advice** | Untouched | **PASS** |
| **Tech constraints** | Python; infra unchanged this PR (explicit out of scope; Terraform remains canonical for future infra) | **PASS** |

**Gate evaluation**: PASS — proceed. No unjustified complexity.

## Technical Decisions

### 1. Concurrency mechanism and config knob (CA-1)

| Decision | Choice |
|----------|--------|
| Mechanism | `concurrent.futures.ThreadPoolExecutor` for embed calls inside `ChunkIndexer.upsert_chunks` |
| Rationale | Bedrock `invoke_model` is I/O-bound; threads avoid asyncio rewrite of boto3 clients; matches current sync `TitanEmbedClient.embed` |
| Knob | Constructor arg `embed_concurrency: int` on `ChunkIndexer` (default **8**); mirrored by env `SEC_SIGNALS_EMBED_CONCURRENCY` on `Settings` / worker wiring |
| Bounds | Must be ≥ 1; values &lt; 1 rejected. `1` = sequential embeds (debug/safe mode) |
| Scope | Only chunks missing `embedding` are submitted to the pool; pre-embedded chunks skip Bedrock |

Grounding: today `indexer.py` loops sequentially `embed` → `client.index` per chunk.

### 2. OpenSearch bulk batching (CA-1)

| Decision | Choice |
|----------|--------|
| API | OpenSearch `_bulk` via new protocol method on `SearchIndexerClient` (e.g. `bulk(body=...)` / operations list) while keeping single-doc `index` for compatibility if needed |
| Batch size | Config knob `opensearch_bulk_size: int` default **50** (env `SEC_SIGNALS_OPENSEARCH_BULK_SIZE`); flush when full and flush remainder at end |
| Document body | Same fields as current per-doc upsert (`chunk_id`, ticker/cik/accession/form/`filing_date`/section/item/text/offsets/`embedding`) |
| Ordering | Embed phase may complete out of order; bulk batches group completed docs; progress count increments as docs are successfully bulk-written (or as each chunk finishes embed+enqueue — prefer count after successful write of that chunk’s batch membership is committed; see progress below) |

### 3. Retry / backoff policy (CA-3)

Shared helper (e.g. `sec_signals.retrieve.retry.call_with_backoff`) used by Titan embed and OpenSearch bulk/index:

| Parameter | Value |
|-----------|--------|
| Max attempts | **5** (1 initial + 4 retries) |
| Backoff | Exponential: `base_delay * (2 ** (attempt - 1))` with `base_delay = 0.5` seconds |
| Jitter | Full jitter in `[0, delay]` to reduce thundering herd under concurrency |
| Retriable | Bedrock: `ThrottlingException`, `ServiceUnavailableException`, `ModelTimeoutException`, HTTP 429/5xx when exposed; OpenSearch: transport/HTTP 429 or 503, connection errors; **and** bulk HTTP 200 responses with `errors: true` where failed items report status **429 or 503** (retry **those failed items only**, within the same max-attempt budget) |
| Bulk item handling | After every `bulk` call, inspect the top-level `errors` flag and each item’s status. Count a chunk toward `indexed X/Y` only after its item succeeds. Items that remain unrecovered after max attempts (or that fail with non-retriable statuses) **MUST fail the run** — never log `indexed Y/Y` with missing chunks |
| Non-retriable | 4xx validation/auth (except 429), schema/programming errors, bulk item failures other than 429/503 — fail immediately (or after unrecovered retries for 429/503) |
| Tests | Mocked clients that fail N times then succeed; assert call count and that sleep/backoff is invoked (monkeypatch sleep); include a **mixed-success** bulk response (some items ok, one item status 429) that is retried until that item succeeds |

### 4. Progress log format (CA-2)

- Logger: existing `sec_signals.logging_utils` / module logger on indexer.
- Exact message substring / format: **`indexed X/Y chunks`** where `Y = len(chunks)` at start and `X` is the number of chunks successfully written so far after each successful bulk flush (and after final flush). Intermediate lines allowed after each batch; final line MUST be `indexed Y/Y chunks` on success.
- Empty input: log `indexed 0/0 chunks` once or skip; must not raise.

### 5. Package emission schema (CA-4; closes #8)

| Decision | Choice |
|----------|--------|
| Source of truth in repo | Keep canonical contract at `specs/001-10k-signal-demo/contracts/signal-emission.schema.json`; **copy** (or generate-copy in packaging docs) into package data path |
| Package path | `src/sec_signals/schemas/signal-emission.schema.json` |
| Loader | `importlib.resources.files("sec_signals.schemas").joinpath("signal-emission.schema.json").read_text(encoding="utf-8")` in `emission_validator.load_emission_schema` |
| Packaging | `pyproject.toml`: `[tool.setuptools.package-data]` → `"sec_signals" = ["schemas/*.json"]` (and ensure `schemas` is a package with `__init__.py` or use setuptools package-data for non-package dirs — prefer `sec_signals/schemas/` as a package) |
| Worker | No Dockerfile/Terraform change required in this feature if the image installs the package from `src/` via the existing copy of `src/`; schema rides inside the wheel/install. If image does editable-style copy of `src/` only, package-data under `src/sec_signals/schemas/` is included automatically. |
| Test | (1) Assert packaged schema bytes are **identical** to `specs/001-10k-signal-demo/contracts/signal-emission.schema.json`. (2) Build a wheel, install into a **fresh venv outside the repo**, run `load_emission_schema()` from that install, and assert the wheel contains `sec_signals/schemas/signal-emission.schema.json` so the check cannot pass by importing the source-tree copy. Also assert hermetic contract markers on the loaded dict. |

Grounding: `emission_validator._SCHEMA_PATH` resolves to `parents[3]/specs/001-10k-signal-demo/contracts/...` which becomes `/usr/local/lib/python3.12/specs/...` in the image (#8).

### 6. Cost impact (issue notes)

- Titan bills **per input token**, not per call → same corpus, same token cost whether sequential or concurrent.
- Shorter Fargate runtime → compute cost should **not rise** and may fall.
- Risk: Bedrock **throttling** under higher concurrency → mitigated by CA-3 backoff and tunable `embed_concurrency` (lower if throttle rates spike).
- Avoid re-triggering failed SFN retries that re-index the same filing repeatedly (ops note for Jorge on CA-5).

## Project Structure

### Documentation (this feature)

```text
specs/002-fast-indexing/
├── plan.md                 # This file
├── spec.md
├── tasks.md
└── checklists/requirements.md
```

### Source Code (touched by implementation tasks)

```text
src/sec_signals/
├── config.py                          # embed_concurrency, opensearch_bulk_size (+ env)
├── retrieve/
│   ├── indexer.py                     # concurrent embed + bulk + progress
│   ├── titan_embed.py                 # retry wrapper or call sites
│   └── retry.py                       # NEW shared backoff helper (optional module)
├── schemas/
│   ├── __init__.py                    # NEW
│   └── signal-emission.schema.json    # NEW packaged copy of contract
└── validate/
    └── emission_validator.py          # importlib.resources loader

pyproject.toml                         # package-data for schemas/*.json

tests/
├── unit/
│   ├── test_indexer_concurrency.py    # CA-1
│   ├── test_indexer_progress.py       # CA-2
│   ├── test_embed_opensearch_retry.py # CA-3
│   └── test_emission_schema_packaged.py  # CA-4
```

**Structure Decision**: Single-package Python layout; no new services or infra modules in this feature.

## Complexity Tracking

> No constitution violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Implementation Notes (non-goals reminder)

- Do **not** edit `section_chunker.py` `max_chars`.
- Do **not** change `DEFAULT_EMBED_MODEL_ID` / dimensions.
- Do **not** open Terraform/IAM PRs for this issue.
- CA-5 evidence is Jorge’s rebuild/push + SFN re-trigger after code merges.
