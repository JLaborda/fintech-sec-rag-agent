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
