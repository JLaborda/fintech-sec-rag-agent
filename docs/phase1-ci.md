# Phase-1 CI notes

- Always: `pytest tests/contract tests/unit`
- Integration tests may require AWS stubs; run locally with `pytest tests/integration`
- LLM-as-judge (`tests/golden -m llm_judge`) runs only when RAG surfaces change:
  - `src/sec_signals/{retrieve,extract,validate,warehouse,pipeline}/`
  - prompts / factor schema / contracts
- Required secrets/env for live judge or ingest (never commit values):
  - Bedrock access in `eu-west-1`
  - `SEC_EDGAR_USER_AGENT`
  - optional `DEMO_API_KEY`
