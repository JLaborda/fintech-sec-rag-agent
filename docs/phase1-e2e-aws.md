# Phase-1 live AWS E2E (account required)

Unit/contract tests mock AWS. The following needs a real `eu-west-1` account with credentials.

## Blocked without credentials / account setup

| Step | Needs |
|------|-------|
| `terraform apply` in `infra/envs/demo` | AWS credentials + permissions for S3, AOSS, ECS/ECR, SFN, Lambda, API GW, IAM, EventBridge, Glue, Athena |
| Bedrock Converse Haiku 4.5 | Model access for `eu.anthropic.claude-haiku-4-5-20251001-v1:0` |
| Titan embeddings | Model access for `amazon.titan-embed-text-v2:0` |
| `sec-signals ingest` | `SEC_EDGAR_USER_AGENT`, `SEC_SIGNALS_RAW_BUCKET`, network to `data.sec.gov` / `www.sec.gov` |
| Primary path Fargate | Docker image pushed to ECR (`docker build` + `docker push` to `ecr_repository_url`) |
| Secondary Lambda API | `scripts/package_emit_lambda.sh` → pass `-var=lambda_package_path=…/dist/emit_lambda.zip` |
| AOSS data plane | Terraform data-access policy principals (Fargate + Lambda roles) + `aoss:APIAccessAll` |
| Athena verification | Glue table + workgroup from TF outputs |

## Deploy sequence (when credentials exist)

```bash
# 1) Package secondary Lambda (optional for first apply; stub ships by default)
./scripts/package_emit_lambda.sh

# 2) Terraform
cd infra/envs/demo
terraform init
terraform apply -var="aws_region=eu-west-1" \
  -var="lambda_package_path=$PWD/../../../dist/emit_lambda.zip"

# 3) Build/push Fargate image
aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin "$ACCOUNT.dkr.ecr.eu-west-1.amazonaws.com"
docker build -t sec-signals-worker:0.1.0 .
docker tag sec-signals-worker:0.1.0 "$(terraform output -raw ecr_repository_url):latest"
docker push "$(terraform output -raw ecr_repository_url):latest"

# 4) Export runtime env for CLI
export AWS_REGION=eu-west-1
export SEC_SIGNALS_RAW_BUCKET="$(terraform output -raw bucket)"
export SEC_SIGNALS_AOSS_ENDPOINT="$(terraform output -raw aoss_endpoint)"
export SEC_EDGAR_USER_AGENT="YourOrg contact@example.com"

# 5) Land filings → EventBridge → SFN → Fargate
sec-signals ingest --tickers V,MA,PYPL,XYZ,COIN

# 6) Secondary re-emit (debug/backfill only)
sec-signals emit --tickers V --persist-warehouse
```

## What CI covers without AWS

- Contract + unit tests (including mocked live-wiring factories)
- No live Bedrock / AOSS / EDGAR calls in default CI
