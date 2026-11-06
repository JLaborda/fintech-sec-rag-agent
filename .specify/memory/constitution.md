# SEC Qualitative Signals RAG Constitution

## Core Principles

### I. Hermetic Qualitative Signals

The system MUST emit a fixed, versioned catalog of qualitative factors per
company (polarity, confidence, and textual citation) as a closed JSON
contract via pipeline, API, or CLI. Runtime MUST NOT invent ad-hoc factors.
When evidence is insufficient for a factor, the system MUST return
`insufficient_evidence` without inventing polarity, while still completing
the hermetic schema. Conversational interfaces, if any, MUST NOT bypass this
contract.

Rationale: Downstream portfolio consumers need a stable, machine-checkable
signal surface—one signal among many—not free-form prose.

### II. Auditable Provenance

SEC EDGAR is the canonical filing source. Raw 10-K / 10-K/A objects MUST be
stored immutably in an S3 (or S3-compatible) datalake keyed for
reproducibility; vector indexes are derived and MUST be rebuildable from
the lake. Every emitted factor with evidence MUST include at least: ticker,
cik, accession_number, filing_date, form, section (or item), quote (and
offsets when available), factor_id, factor-schema version, and
model_or_pipeline_version. A signal lacking required provenance MUST NOT
be emitted as a scored factor.

Rationale: Rigor and traceability for audits require end-to-end lineage from
EDGAR through extraction.

### III. Phased Scope Discipline

Demo / v1 scope is the RAG → auditable qualitative signals path only
(ingest, retrieve, hermetic extract, export). Portfolio ranking (composite
score / alerts with factor-level traceability, no broker) is a planned
phase-2 capability. Paper-broker integration is aspirational phase-3.
Later phases MUST consume the signal contract; they MUST NOT weaken
hermeticity, provenance, or evaluation gates of the signal pipeline.

Rationale: Ship a deployable signal system first; aggregation and action
layers build on a trustworthy contract.

### IV. Verifiable Quality Gates

Contract tests against the hermetic JSON schema, sample 10-K fixtures, and
provenance rules (including correct `insufficient_evidence` behavior) are
mandatory gates. LLM-as-judge evaluation over a canonical golden set MUST
run in CI when RAG-related surfaces change (retrieval, prompts, factor
schema, signal pipeline)—not when only unrelated systems (e.g. portfolio
aggregator) change. LLM-as-judge MUST NOT be required on every production
request in v1.

Rationale: Cheap deterministic gates catch contract drift; bounded judge
evals catch grounding/quality regressions without unbounded cost.

### V. Research Signals, Not Investment Advice

Outputs are research / decision-support signals intended to be aggregated
into portfolio workflows. They MUST NOT be presented as financial advice or
investment recommendations. API, CLI, ranking, and any future paper-broker
surfaces MUST carry this framing.

Rationale: Keeps product intent aligned with auditability and responsible
use as signals feed portfolio construction.

## Phased Delivery Roadmap

- **Phase 1 (demo):** EDGAR 10-K / 10-K/A ingest → S3 raw lake → RAG →
  hermetic factor JSON for a defined universe; Terraform-deployable on AWS.
- **Phase 2:** Portfolio ranking / alerts with traceability back to each
  factor and citation; no live order execution.
- **Phase 3 (aspirational):** Paper-broker integration for simulated action
  on ranked signals.

Corpus expansion beyond 10-K / 10-K/A requires an explicit constitution or
spec amendment.

## Technology & Deployment Constraints

- **Language:** Python is the primary implementation language for ingest,
  RAG, hermetic extraction, and evals.
- **Infrastructure:** Terraform is the canonical IaC. The demo MUST be
  deployable to AWS from the repo (minimum: S3 datalake + pipeline/API
  runtime path). Local stubs MUST honor the same storage/API contracts.
- **Factor catalog:** Versioned in-repo (schema + definitions). Additions,
  removals, or renames MUST bump factor-schema semver; historical signals
  retain the schema version under which they were emitted.

## Governance

This constitution supersedes conflicting informal practice for in-scope
work. Amendments require an updated constitution document, semver bump, and
brief sync notes (what changed and why):

- **MAJOR:** Remove or redefine a principle in a backward-incompatible way.
- **MINOR:** Add a principle/section or materially expand guidance.
- **PATCH:** Clarifications, wording, non-semantic refinements.

Features that touch RAG, factor schema, provenance, or the signal contract
MUST follow Spec Kit: specify → plan → tasks → implement (clarify/analyze
as needed). Cosmetic docs or trivial infra that cannot affect those
surfaces MAY proceed without a full spec cycle. PRs affecting in-scope
surfaces SHOULD be reviewed for constitution compliance. Runtime
development guidance lives alongside Spec Kit artifacts under `.specify/`.

**Version**: 1.0.0 | **Ratified**: 2026-11-06 | **Last Amended**: 2026-11-06
