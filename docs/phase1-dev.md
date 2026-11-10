# Phase-1 developer notes

See Spec Kit quickstart: [`specs/001-10k-signal-demo/quickstart.md`](../specs/001-10k-signal-demo/quickstart.md).

## Locked stack

| Concern | Value |
|---------|-------|
| Region | `eu-west-1` |
| LLM | `eu.anthropic.claude-haiku-4-5-20251001-v1:0` (Bedrock Converse) |
| Embeddings | `amazon.titan-embed-text-v2:0` @ 1024-d |
| Vector (RAG only) | OpenSearch Serverless |
| Durable signals | S3 curated Parquet + Glue + Athena |
| Primary path | S3 raw → Step Functions → Fargate (index + emit + warehouse) |
| Secondary | CLI / API Gateway Lambda re-emit / backfill |

## Local setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest tests/contract tests/unit -q
```

## Fetch latest 10-K (demo)

SEC requires an identifiable User-Agent (never commit a real email):

```bash
export SEC_EDGAR_USER_AGENT="YourOrg contact@example.com"
```

**Local HTML only** (no S3 — useful for interviews):

```bash
uv run python scripts/fetch_10k.py --tickers V
# writes under data/local/edgar/<cik>/<accession>/
```

**Production lake** (lands raw object → primary S3→SFN→Fargate path):

```bash
export SEC_SIGNALS_RAW_BUCKET="<bucket>"
uv run sec-signals ingest --tickers V
```

`EdgarClient` throttles ~8 req/s (same idea as SmartWealthAI `sec_client`). Full 10-K
HTML fetch already lived in this package; SmartWealthAI’s spike downloaded `companyfacts`
JSON, not filing HTML.

## Live AWS (optional)

See [`phase1-e2e-aws.md`](phase1-e2e-aws.md). Required env for CLI / Fargate:

- `SEC_SIGNALS_RAW_BUCKET`
- `SEC_SIGNALS_AOSS_ENDPOINT`
- `SEC_EDGAR_USER_AGENT` (ingest)
- Bedrock access for Haiku 4.5 + Titan V2 in `eu-west-1`
