# Data Model: Phase-1 SEC 10-K Qualitative Signal Generator

**Feature**: `001-10k-signal-demo` | **Schema version**: `0.1.0` | **Date**: 2026-11-06

Aligned to locked contract v0.1 and constitution provenance rules. Implementation models SHOULD map 1:1 to these entities and to `contracts/signal-emission.schema.json`. Durable analytics persistence follows `contracts/signal-warehouse.md`.

## Enumerations

### FormType
- `10-K`
- `10-K/A`

### FactorId (closed catalog — no runtime additions)
1. `regulatory_and_legal_risk`
2. `competitive_position`
3. `management_tone`
4. `demand_and_growth_outlook`
5. `operational_and_supply_risk`

### FactorStatus
- `ok` — evidence present; polarity/conviction/quote/reasoning required
- `insufficient_evidence` — no polarity; reasoning explains search gap

### DemoTicker
- `V`, `MA`, `PYPL`, `XYZ`, `COIN`

## Entities

### Filing

Canonical EDGAR submission retained immutably in the raw lake.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `ticker` | DemoTicker | yes | |
| `cik` | string | yes | Zero-padded CIK as used by EDGAR |
| `accession_number` | string | yes | EDGAR accession |
| `form` | FormType | yes | `10-K` or `10-K/A` |
| `filing_date` | date (ISO `YYYY-MM-DD`) | yes | Published filing date |
| `source_urls` | string[] | yes | EDGAR URLs used |
| `raw_s3_uri` | string | yes | Immutable object URI |
| `primary_document` | string | yes | Filing primary doc name |
| `ingested_at` | datetime | yes | Pipeline clock |

**Rules**:
- Latest filing for emit = max(`filing_date`) among `10-K`/`10-K/A` for ticker (tie-break: newest accession).
- Raw objects are never overwritten; new ingest creates new keys or fails if identical content already present.
- **Creating a new raw filing object MUST trigger the primary index → emit → warehouse pipeline.**

**Relationships**: 1 Filing → many Chunks; 0..1 SignalEmission per (Filing, `model_or_pipeline_version`) for default emit; many SignalFactorRow warehouse rows per emission.

---

### Chunk

Section-aware excerpt used for retrieval and citation.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `chunk_id` | string | yes | Stable within accession |
| `ticker` | DemoTicker | yes | Copied from Filing |
| `cik` | string | yes | |
| `accession_number` | string | yes | |
| `form` | FormType | yes | |
| `filing_date` | date | yes | **Must** be in vector metadata |
| `section` | string | yes | Human section label |
| `item` | string | yes | e.g. `Item 1A` |
| `text` | string | yes | Chunk body |
| `char_start` | int \| null | no | Offset when available |
| `char_end` | int \| null | no | Offset when available |
| `embedding` | float[1024] | yes (indexed) | Titan V2; not echoed in signal JSON |

**Rules**:
- Vector index is derived; deleting AOSS documents and re-embedding from S3 MUST restore equivalent retrieval metadata.
- Retrieval filters MUST be able to constrain on `filing_date`, `ticker`, `accession_number`.
- AOSS holds chunks for RAG only — never treat AOSS documents as the durable signal table.

**Relationships**: Chunk → Filing (N:1).

---

### Citation

Pointer from a scored factor back into a filing chunk/section.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `section` | string | yes | |
| `item` | string | yes | |
| `quote` | string | yes | Verbatim excerpt from filing text |
| `char_start` | int \| null | no | |
| `char_end` | int \| null | no | |
| `chunk_id` | string \| null | no | When resolvable |

**Rules**:
- `ok` factors MUST include a non-empty `quote` and section/item.
- Validator rejects `ok` factors without citation.

---

### FactorSignal

One of five hermetic catalog members on an emission.

#### When `status = ok`

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `factor_id` | FactorId | yes | |
| `status` | `"ok"` | yes | |
| `polarity` | float | yes | ∈ [-1.0, 1.0] |
| `conviction` | float | yes | ∈ [0.0, 1.0] |
| `citation` | Citation | yes | |
| `reasoning` | string | yes | ~2–4 sentences; this factor only |

#### When `status = insufficient_evidence`

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `factor_id` | FactorId | yes | |
| `status` | `"insufficient_evidence"` | yes | |
| `polarity` | — | **forbidden** | Must be absent |
| `conviction` | float \| null | no | Prefer absent |
| `citation` | Citation \| null | no | Prefer absent |
| `reasoning` | string | yes | Must state what was searched / why insufficient |

---

### KeyEvent (optional)

Cited factual highlight at filing level — **not** a sixth polarity factor.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `summary` | string | yes | Short factual highlight |
| `citation` | Citation | yes | Must be cited |

---

### SignalEmission

Hermetic JSON document produced by the primary on-ingest pipeline (and by secondary CLI/API re-emit). Logical contract object before warehouse flattening.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `factor_schema_version` | `"0.1.0"` | yes | Locked |
| `model_or_pipeline_version` | string | yes | Semver or git SHA of pipeline/prompts |
| `ticker` | DemoTicker | yes | |
| `cik` | string | yes | |
| `accession_number` | string | yes | |
| `form` | FormType | yes | |
| `filing_date` | date | yes | Same as Filing |
| `factors` | FactorSignal[5] | yes | Exactly the five FactorIds, each once |
| `key_events` | KeyEvent[] | no | May be empty/omitted |
| `disclaimer` | string | yes | Research-not-advice framing |
| `emitted_at` | datetime | yes | |

**Validation rules** (enforced before emit / warehouse write):
1. Exactly five factors; set of `factor_id` == closed catalog.
2. No ad-hoc factor ids.
3. Every `ok` factor has in-range polarity/conviction + citation quote.
4. Every `insufficient_evidence` factor omits polarity.
5. Filing-level provenance complete including `filing_date`.
6. Uncited or provenance-incomplete scored claims are **dropped** (converted to `insufficient_evidence` or rejected per validator policy — Phase-1 policy: **drop scored claim → emit `insufficient_evidence` with reasoning noting validation drop**).

**Relationships**: SignalEmission → Filing (N:1); SignalEmission contains FactorSignals (1:5); SignalEmission → SignalFactorRow (1:5).

---

### SignalFactorRow (warehouse / curated table)

Tabular durable form of one factor on one emission. **Authoritative analytics store** (Glue/Athena over Parquet). One emission yields exactly five rows.

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| `factor_schema_version` | string | yes | Partition / column; const `0.1.0` |
| `ticker` | DemoTicker | yes | **Partition key** |
| `filing_date` | date | yes | **Partition key** (`YYYY-MM-DD`) |
| `cik` | string | yes | |
| `accession_number` | string | yes | |
| `form` | FormType | yes | |
| `model_or_pipeline_version` | string | yes | |
| `emitted_at` | datetime | yes | |
| `factor_id` | FactorId | yes | |
| `status` | FactorStatus | yes | |
| `polarity` | float \| null | conditional | Required when `ok`; null when `insufficient_evidence` |
| `conviction` | float \| null | no | |
| `citation_section` | string \| null | conditional | Required when `ok` |
| `citation_item` | string \| null | conditional | Required when `ok` |
| `citation_quote` | string \| null | conditional | Required when `ok` |
| `citation_char_start` | int \| null | no | |
| `citation_char_end` | int \| null | no | |
| `citation_chunk_id` | string \| null | no | |
| `reasoning` | string | yes | |
| `disclaimer` | string | yes | Copied from emission |
| `key_events_json` | string \| null | no | Optional JSON-serialized `key_events` on each of the five rows (same payload) |

**Storage layout**:
```text
s3://{bucket}/curated/signals/
  factor_schema_version=0.1.0/
    ticker={TICKER}/
      filing_date={YYYY-MM-DD}/
        part-{accession}-{pipeline_version}.parquet
```

**Glue / Athena**:
- Database: `sec_signals` (Terraform-configurable name)
- Table: `curated_signals`
- Partition projection or MSCK/Glue crawler over `ticker`, `filing_date` (and schema version prefix)
- Natural grain: `(ticker, accession_number, factor_schema_version, model_or_pipeline_version, factor_id)`

**Rules**:
- Warehouse write happens **after** successful validation on the primary on-ingest path (and on secondary re-emit).
- Re-emit with the same natural key **overwrites** the Parquet object for that accession/pipeline version (or writes a new pipeline_version object — prefer new `model_or_pipeline_version` for auditability).
- OpenSearch MUST NOT be queried as the durable signal store.

---

### GoldenCase (eval)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `case_id` | string | yes | |
| `ticker` | DemoTicker | yes | |
| `fixture_filing_ref` | string | yes | Path under `fixtures/` |
| `factor_id` | FactorId | yes | |
| `expected_status` | FactorStatus | yes | |
| `judge_rubric` | string | yes | Grounding / citation checks |
| `rag_surface_tags` | string[] | yes | Used to gate CI |

## State transitions

```text
[EDGAR] --fetch--> Filing(raw in S3)
Filing raw object-created --S3 event--> Step Functions / Fargate
Filing --parse/chunk--> Chunk[]
Chunk[] --embed/index--> AOSS documents (derived RAG only)
Filing + AOSS --retrieve+Haiku extract--> draft SignalEmission
draft --validate--> SignalEmission
SignalEmission --flatten--> SignalFactorRow[5]
SignalFactorRow[] --persist--> S3 curated Parquet + Glue/Athena  (DURABLE)
SignalEmission --optional debug--> S3 signals/*.json
Secondary CLI/API re-emit --same library--> validate → warehouse write (backfill/debug only)
```

No portfolio/ranking states in Phase 1.

## Identity & keys

| Entity | Natural key |
|--------|-------------|
| Filing | `(cik, accession_number)` |
| Chunk | `(accession_number, chunk_id)` |
| SignalEmission | `(ticker, accession_number, factor_schema_version, model_or_pipeline_version)` |
| SignalFactorRow | `(ticker, accession_number, factor_schema_version, model_or_pipeline_version, factor_id)` |
