# Feature Specification: Phase-1 SEC 10-K Qualitative Signal Generator

**Feature Branch**: `001-10k-signal-demo`

**Created**: 2026-11-06

**Status**: Draft

**Input**: User description: "Build the phase-1 AWS-native SEC 10-K qualitative signal generator (horizontal slice): ingest latest 10-K/10-K/A from EDGAR for tickers V, MA, PYPL, XYZ, COIN into immutable S3; section-aware parse/chunk with metadata including filing_date; embed/retrieve via AWS (Bedrock embeddings + AWS vector store TBD in plan); emit hermetic JSON signals per locked contract v0.1; schema validator drops uncited scores; CLI/API batch emit; Terraform-deployable happy path; contract tests + fixtures; LLM-as-judge golden set in CI when RAG changes. Research-not-advice. Out of scope: ranking, paper broker, 10-Q/8-K/news, chat-first UX."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Emit hermetic signals for the demo universe (Priority: P1)

A research engineer needs a batch of machine-checkable qualitative signals for tickers V, MA, PYPL, XYZ, and COIN, derived only from each company’s latest 10-K or 10-K/A on EDGAR. For each ticker the system returns a closed JSON payload covering exactly the five locked factors, with provenance and citations, so a downstream aggregator can consume signals without free-form prose.

**Why this priority**: Hermetic, provenance-complete signal emission is the sole Phase-1 product outcome; without it the demo has no consumer value.

**Independent Test**: Run a batch emit for the five tickers against available filings (or fixtures) and verify every returned payload validates against factor schema `0.1.0`, includes required provenance, and never invents polarity when evidence is insufficient.

**Acceptance Scenarios**:

1. **Given** the latest 10-K or 10-K/A for ticker V is available in the immutable filing store, **When** a batch emit is requested for V, **Then** the system returns one hermetic JSON signal set with `factor_schema_version` `0.1.0` covering exactly the five locked factors and full required provenance (`ticker`, `cik`, `accession_number`, `form`, `filing_date`, `model_or_pipeline_version`).
2. **Given** evidence is insufficient for one factor (e.g. `operational_and_supply_risk`), **When** signals are emitted, **Then** that factor has `status` `insufficient_evidence`, has no invented `polarity`, and its `reasoning` explains what was searched and why evidence was insufficient, while the remaining factors may still be `ok`.
3. **Given** a scored factor (`status` `ok`), **When** the payload is validated, **Then** it includes `polarity` in [-1.0, 1.0], `conviction` in [0.0, 1.0], a filing citation (`quote` with section/item and offsets when available), and short `reasoning` of about 2–4 sentences for that factor only.
4. **Given** any emission attempt, **When** a scored factor lacks required provenance or citation, **Then** the schema validator rejects that scored claim and it is not emitted as a scored factor.

---

### User Story 2 - Ingest and section-aware index latest filings (Priority: P1)

A platform operator needs the latest 10-K / 10-K/A for each demo ticker pulled from EDGAR into an immutable object store, then parsed into section-aware chunks with metadata (including `filing_date`) so retrieval can ground signal extraction.

**Why this priority**: Signals without auditable raw filings and searchable chunks cannot satisfy provenance or quality gates.

**Independent Test**: Trigger ingest for the five tickers and confirm raw objects are stored immutably, chunks carry filterable `filing_date` and section/item metadata, and the vector index can be rebuilt from the raw store alone.

**Acceptance Scenarios**:

1. **Given** EDGAR has a current 10-K or 10-K/A for MA, **When** ingest runs for MA, **Then** the raw filing is stored immutably under a reproducible key and is the canonical source for later rebuilds of derived indexes.
2. **Given** a stored filing, **When** section-aware parse/chunk runs, **Then** each chunk includes metadata at least for ticker/CIK/accession, form, `filing_date`, and section/item suitable for citation and retrieval filtering.
3. **Given** an existing raw lake for the demo universe, **When** the derived vector index is deleted and rebuilt, **Then** the rebuilt index is equivalent for retrieval purposes and still exposes `filing_date` in chunk metadata.

---

### User Story 3 - Operate emit via CLI and API (Priority: P2)

An operator or integrator needs to request batch signal emission through both a command-line interface and an HTTP API using the same contract, without a chat-first experience.

**Why this priority**: Batch CLI/API is the mandated Phase-1 delivery surface for the aggregator; chat UX is explicitly out of scope.

**Independent Test**: Emit the same ticker set via CLI and via API and confirm both produce schema-valid payloads with identical required fields and research-not-advice framing.

**Acceptance Scenarios**:

1. **Given** indexed filings for PYPL, XYZ, and COIN, **When** the operator runs a CLI batch emit for those tickers, **Then** hermetic JSON signals are written/returned for each ticker that has a usable filing.
2. **Given** the same indexed state, **When** an authorized client calls the batch emit API for those tickers, **Then** responses match the same hermetic contract and framing as the CLI.
3. **Given** any CLI or API response surface, **When** signals are presented, **Then** they are framed as research / decision-support signals, not investment advice or recommendations.

---

### User Story 4 - Deploy the happy path and gate quality in CI (Priority: P2)

A platform engineer needs a constitution-compliant, infrastructure-as-code deployable happy path for the demo cloud environment, plus mandatory contract tests with fixtures and an LLM-as-judge golden set that runs in CI when RAG-related surfaces change.

**Why this priority**: Phase-1 must be demonstrably deployable and prevented from silent contract or grounding regressions.

**Independent Test**: Apply the documented happy-path deploy in a demo cloud account (or documented dry-run equivalent) and run the contract/fixture suite plus the judge golden set when a retrieval or prompt change is introduced.

**Acceptance Scenarios**:

1. **Given** repository infrastructure-as-code for the demo, **When** the happy-path deploy is applied with required configuration, **Then** the immutable filing store and the pipeline/API runtime path required for ingest→emit are available in the mandated cloud environment.
2. **Given** contract tests and sample 10-K fixtures, **When** CI runs on a change that touches the signal pipeline, **Then** schema, provenance, and `insufficient_evidence` behaviors are asserted and failing tests block merge.
3. **Given** a change to retrieval, prompts, factor schema, or the signal pipeline, **When** CI runs, **Then** the LLM-as-judge golden set executes; **Given** a change that does not touch RAG-related surfaces, **When** CI runs, **Then** the judge suite is not required.

---

### Edge Cases

- Latest filing is a 10-K/A rather than a 10-K: system MUST ingest and emit against that amendment with `form` correctly set to `10-K/A`.
- EDGAR has no usable 10-K / 10-K/A for a requested ticker: batch emit MUST fail that ticker clearly without inventing scores for other tickers’ success path.
- Partial evidence: some factors `ok`, others `insufficient_evidence` in the same hermetic payload.
- Quote/citation missing or unverifiable for a proposed scored factor: validator MUST drop the scored claim (no unscored polarity leak).
- Polarity or conviction outside allowed ranges: validator MUST reject the emission for that factor.
- Duplicate or superseded filings: “latest” means the most recent applicable 10-K or 10-K/A by filing date for the ticker; superseded raw objects remain immutable in the lake but are not selected for emit unless explicitly requested (default: latest only).
- Optional `key_events` present: MUST be cited factual highlights only; MUST NOT act as a sixth polarity factor.
- Downstream consumer requests ranking, portfolio aggregation, paper-broker action, 10-Q/8-K/news, or chat UX: out of scope; system MUST NOT claim to provide those in Phase 1.

## Requirements *(mandatory)*

### Functional Requirements

#### Corpus, universe, and product surface

- **FR-001**: System MUST support ingest and signal emission only for SEC forms `10-K` and `10-K/A` sourced from EDGAR as the canonical filing source.
- **FR-002**: Demo universe MUST be exactly the tickers `V`, `MA`, `PYPL`, `XYZ`, and `COIN`.
- **FR-003**: System MUST expose batch signal emission via CLI and API; chat-first UX is out of scope for this feature.
- **FR-004**: Outputs MUST be framed as research / decision-support signals and MUST NOT be presented as financial advice or investment recommendations.

#### Hermetic factor contract (locked v0.1 / schema `0.1.0`)

- **FR-005**: System MUST emit a closed, versioned qualitative factor catalog per company and MUST NOT invent ad-hoc factors at runtime.
- **FR-006**: Factor schema version for this feature MUST be `0.1.0`, and every emission MUST include `factor_schema_version` set to `0.1.0`.
- **FR-007**: Every emission MUST include exactly these five factors (no more, no fewer as catalog members):
  1. `regulatory_and_legal_risk`
  2. `competitive_position`
  3. `management_tone`
  4. `demand_and_growth_outlook`
  5. `operational_and_supply_risk`
- **FR-008**: When evidence exists for a factor, that factor MUST use `status` `ok` and MUST include: `polarity` (float in [-1.0, 1.0]), `conviction` (float in [0.0, 1.0]), citation into the filing via `quote` (section/item + text; offsets when available), and `reasoning` of about 2–4 sentences explaining how the score was derived for that factor only.
- **FR-009**: When evidence is insufficient for a factor, that factor MUST use `status` `insufficient_evidence`, MUST NOT invent `polarity`, and MUST include `reasoning` that states what was searched and why evidence was insufficient, while still completing the hermetic schema for all five factors.
- **FR-010**: Emissions MAY include optional filing-level `key_events` as a list of cited factual highlights; `key_events` MUST NOT be treated as a sixth polarity factor.

#### Provenance and validation

- **FR-011**: Every emission MUST include filing-level provenance of at least: `ticker`, `cik`, `accession_number`, `form` (`10-K` or `10-K/A`), `filing_date` (published date of the filing), and `model_or_pipeline_version`.
- **FR-012**: Every factor emitted with evidence (`status` `ok`) MUST include auditable citation fields aligned with the constitution: section/item, `quote` (and offsets when available), and identity of the factor, in addition to the filing-level provenance in FR-011.
- **FR-013**: `filing_date` MUST appear in the signal JSON payload AND in vector-store chunk metadata so it is filterable and auditable at retrieve time.
- **FR-014**: A schema validator MUST run before emission; scored claims that lack required provenance or citation MUST be dropped and MUST NOT be emitted as scored factors.
- **FR-015**: Signals lacking required provenance MUST NOT be emitted as scored factors.

#### Ingest, storage, retrieve, emit path

- **FR-016**: System MUST ingest the latest applicable 10-K or 10-K/A per demo ticker from EDGAR into an immutable object store keyed for reproducibility (constitution-mandated cloud object lake).
- **FR-017**: System MUST perform section-aware parse and chunk of stored filings, attaching metadata required for citation and retrieval (including `filing_date` and section/item).
- **FR-018**: System MUST embed and retrieve chunks on the mandated cloud-native path so extraction is grounded in retrieved filing text; chunk metadata MUST remain filterable by `filing_date` at retrieve time.
- **FR-019**: Vector indexes MUST be treated as derived artifacts rebuildable from the immutable raw lake.
- **FR-020**: System MUST support an infrastructure-as-code deployable happy path on the mandated cloud covering at least the immutable filing store and the pipeline/API runtime needed for ingest through emit.

#### Quality gates

- **FR-021**: Repository MUST include contract tests and sample 10-K fixtures that assert hermetic schema compliance, provenance rules, and correct `insufficient_evidence` behavior; these gates are mandatory.
- **FR-022**: An LLM-as-judge evaluation over a canonical golden set MUST run in CI when RAG-related surfaces change (retrieval, prompts, factor schema, signal pipeline) and MUST NOT be required on every production request in Phase 1; unrelated non-RAG changes MUST NOT force the judge suite.

#### Explicit non-goals (Phase 1)

- **FR-023**: System MUST NOT implement portfolio ranking, composite scoring alerts, or paper-broker / order simulation in this feature.
- **FR-024**: System MUST NOT ingest or score from 10-Q, 8-K, news, or other non-10-K / 10-K/A sources in this feature without a separate constitution/spec amendment.

### Key Entities

- **Filing (10-K / 10-K/A)**: Canonical EDGAR submission for a company; identified by ticker, CIK, accession number, form, and `filing_date`; stored immutably as raw object.
- **Chunk**: Section-aware excerpt of a filing used for retrieval; carries metadata including `filing_date`, section/item, and identifiers needed to rebuild citations.
- **Factor signal**: One of the five locked catalog members for a company emission; either `ok` (polarity, conviction, quote, reasoning) or `insufficient_evidence` (reasoning only; no polarity).
- **Signal emission**: Hermetic JSON document for one ticker/filing with `factor_schema_version` `0.1.0`, `model_or_pipeline_version`, full provenance, the five factors, and optional cited `key_events`.
- **Golden evaluation case**: Fixture used by contract tests and/or LLM-as-judge to assert grounding and contract behavior when RAG surfaces change.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For all five demo tickers with a usable latest 10-K or 10-K/A, a single batch emit produces five hermetic payloads that each validate against factor schema `0.1.0` with no missing catalog factors.
- **SC-002**: 100% of emitted `ok` factors include in-range polarity and conviction, a filing citation, and short per-factor reasoning; 100% of `insufficient_evidence` factors omit invented polarity and explain the evidence gap.
- **SC-003**: 100% of emitted payloads include required provenance fields, including `filing_date`; validator rejects unscored/uncited scored claims in fixture-based tests before any consumer would see them.
- **SC-004**: Operators can complete a documented happy-path deploy and a batch emit for the demo universe without manual patching of the signal contract.
- **SC-005**: Contract/fixture suite catches schema and provenance regressions on every relevant CI run; LLM-as-judge golden set runs on RAG-related changes and fails the run when grounding quality regresses against the locked golden set.
- **SC-006**: Stakeholder review confirms Phase-1 surfaces are research-not-advice only and that ranking, paper broker, non-10-K sources, and chat-first UX are absent from the delivered demo.

## Assumptions

- Platform constraints from the project constitution apply: primary implementation language Python; Terraform as canonical IaC; AWS as deployment target; immutable raw filings in S3 (or S3-compatible) object storage; Bedrock for embeddings and generation.
- Exact Bedrock model IDs (generation and embedding) are left to `/speckit-plan`.
- Concrete AWS vector store product is left to planning; Phase 1 assumes an AWS-hosted vector store that can persist chunk metadata including `filing_date`.
- “Latest” filing means the most recent 10-K or 10-K/A by `filing_date` for each ticker at ingest/emit time unless an operator explicitly selects another accession.
- Demo-scale throughput only: five tickers, on-demand or scheduled batch, not high-frequency multi-tenant SaaS SLAs.
- Local stubs, if provided, honor the same storage and emit contracts as the cloud path but are not a substitute for the deployable happy-path requirement.
- Authorization for the emit API is environment-appropriate for an internal demo (not a public anonymous API); detailed auth product choice is planning-level.
- Optional `key_events` may be empty or omitted when no high-confidence cited highlights exist.
- North-star institutional pipeline vision informs direction only; this specification does not expand Phase-1 scope to ranking, paper broker, or additional data sources.
