# fintech-sec-rag-agent

AWS-native Phase-1 **SEC 10-K / 10-K/A** qualitative signal generator for demo tickers **V, MA, PYPL, XYZ, COIN**.

## Locked stack

| Concern | Choice |
|---------|--------|
| Region | `eu-west-1` |
| LLM | Bedrock Converse Claude Haiku 4.5 — `eu.anthropic.claude-haiku-4-5-20251001-v1:0` |
| Embeddings | Titan Text Embeddings V2 — `amazon.titan-embed-text-v2:0` (1024-d) |
| Vector (RAG only) | OpenSearch Serverless |
| Durable signals | S3 curated Parquet + Glue + Athena |
| Primary path | S3 raw landing → Step Functions / Fargate (index + emit + warehouse) |
| Secondary | CLI / API Gateway Lambda re-emit / debug / backfill |
| IaC | Terraform under `infra/` |

## Spec Kit

Feature artifacts: [`specs/001-10k-signal-demo/`](specs/001-10k-signal-demo/) (`plan.md`, `tasks.md`, contracts).

Developer notes: [`docs/phase1-dev.md`](docs/phase1-dev.md) · Quickstart: [`specs/001-10k-signal-demo/quickstart.md`](specs/001-10k-signal-demo/quickstart.md)

## Local tests

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest tests/contract tests/unit -q
```

Live AWS wiring (CLI `ingest`/`emit`, Fargate worker, Terraform ECR/ECS/SFN/API) is implemented with mocked unit tests. End-to-end against a real account is documented in [`docs/phase1-e2e-aws.md`](docs/phase1-e2e-aws.md) and remains blocked without credentials + Bedrock model access.

## Scope

Hermetic qualitative signals only. **Out of scope:** ranking, paper broker, 10-Q/8-K/news, chat-first UX. Research / decision-support — not investment advice.

## License / secrets

Do not commit AWS account IDs, API keys, or EDGAR credentials. Use local `.env` (gitignored).
