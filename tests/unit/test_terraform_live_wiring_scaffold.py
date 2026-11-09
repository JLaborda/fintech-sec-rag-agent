"""Guardrails: live-AWS Terraform scaffolds exist beyond Pass-state stubs."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPUTE = (ROOT / "infra" / "modules" / "compute" / "main.tf").read_text(encoding="utf-8")
VECTOR = (ROOT / "infra" / "modules" / "vector" / "main.tf").read_text(encoding="utf-8")
LAKE = (ROOT / "infra" / "modules" / "lake" / "main.tf").read_text(encoding="utf-8")
DEMO = (ROOT / "infra" / "envs" / "demo" / "main.tf").read_text(encoding="utf-8")


def test_compute_has_ecr_ecs_fargate_and_sfn_run_task() -> None:
    assert "aws_ecr_repository" in COMPUTE
    assert "aws_ecs_cluster" in COMPUTE
    assert "aws_ecs_task_definition" in COMPUTE
    assert "ecs:runTask.sync" in COMPUTE
    assert "RunIndexEmit" in COMPUTE
    assert '"Retry"' in COMPUTE or "Retry =" in COMPUTE or "Retry" in COMPUTE
    assert 'Type   = "Pass"' not in COMPUTE or "IgnoredSidecar" in COMPUTE


def test_compute_has_api_gw_lambda_and_eventbridge_trigger() -> None:
    assert "aws_apigatewayv2_api" in COMPUTE
    assert "aws_lambda_function" in COMPUTE
    assert "aws_cloudwatch_event_rule" in COMPUTE
    assert "raw/edgar/" in COMPUTE


def test_batch_emit_route_requires_iam_and_demo_api_key_env() -> None:
    """T037 / spec: emit API is not a public anonymous endpoint."""
    assert 'authorization_type = "AWS_IAM"' in COMPUTE
    assert "DEMO_API_KEY" in COMPUTE
    assert "DEMO_REQUIRE_API_KEY" in COMPUTE
    assert 'aws_ssm_parameter" "demo_api_key"' in COMPUTE
    stub = (ROOT / "infra" / "modules" / "compute" / "lambda_stub_handler.py").read_text(
        encoding="utf-8"
    )
    assert "503" in stub
    assert '"statusCode": 200' not in stub or "/v1/health" in stub


def test_vector_has_network_and_data_policies() -> None:
    assert 'type = "network"' in VECTOR
    assert "aws_opensearchserverless_access_policy" in VECTOR
    assert 'type = "data"' in VECTOR


def test_lake_enables_eventbridge() -> None:
    assert "eventbridge = true" in LAKE


def test_demo_wires_modules_and_outputs() -> None:
    assert "module \"compute\"" in DEMO
    assert "emit_api_endpoint" in DEMO
    assert "ecr_repository_url" in DEMO


def test_dockerfile_and_lambda_packager_exist() -> None:
    assert (ROOT / "Dockerfile").exists()
    assert (ROOT / "scripts" / "package_emit_lambda.sh").exists()
    assert (ROOT / "docs" / "phase1-e2e-aws.md").exists()
