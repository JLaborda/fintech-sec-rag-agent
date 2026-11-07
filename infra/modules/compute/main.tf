terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = ">= 2.4"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.5"
    }
  }
}

variable "name_prefix" {
  type = string
}

variable "lake_bucket" {
  type = string
}

variable "lake_bucket_arn" {
  type = string
}

variable "aoss_collection_name" {
  type = string
}

variable "aoss_endpoint" {
  type = string
}

variable "aws_region" {
  type    = string
  default = "eu-west-1"
}

variable "container_image" {
  type        = string
  description = "Fargate image URI. Defaults to the ECR repo :latest once pushed."
  default     = ""
}

variable "lambda_package_path" {
  type        = string
  description = "Path to emit Lambda zip (built by scripts/package_emit_lambda.sh)."
  default     = ""
}

variable "demo_api_key" {
  type        = string
  description = "x-api-key for secondary batch emit. Empty generates a SecureString in SSM."
  sensitive   = true
  default     = ""
}

variable "tags" {
  type    = map(string)
  default = {}
}

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "sfn_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "events_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
  }
}

resource "aws_ecr_repository" "worker" {
  name                 = "${var.name_prefix}-sec-signals-worker"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  image_scanning_configuration {
    scan_on_push = true
  }
  tags = var.tags
}

resource "aws_cloudwatch_log_group" "pipeline" {
  name              = "/sec-signals/${var.name_prefix}"
  retention_in_days = 14
  tags              = var.tags
}

resource "aws_iam_role" "ecs_execution" {
  name               = "${var.name_prefix}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "fargate_task" {
  name               = "${var.name_prefix}-fargate-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
  tags               = var.tags
}

resource "aws_iam_role_policy" "fargate_task" {
  name = "${var.name_prefix}-fargate-task"
  role = aws_iam_role.fargate_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3Lake"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
        Resource = [
          var.lake_bucket_arn,
          "${var.lake_bucket_arn}/*"
        ]
      },
      {
        Sid      = "Bedrock"
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel", "bedrock:Converse"]
        Resource = ["*"]
      },
      {
        Sid      = "AOSSAPI"
        Effect   = "Allow"
        Action   = ["aoss:APIAccessAll"]
        Resource = ["*"]
      },
      {
        Sid      = "Logs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = ["${aws_cloudwatch_log_group.pipeline.arn}:*"]
      }
    ]
  })
}

resource "aws_iam_role" "emit_lambda" {
  name               = "${var.name_prefix}-emit-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
  tags               = var.tags
}

resource "aws_iam_role_policy" "emit_lambda" {
  name = "${var.name_prefix}-emit-lambda"
  role = aws_iam_role.emit_lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3Lake"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
        Resource = [
          var.lake_bucket_arn,
          "${var.lake_bucket_arn}/*"
        ]
      },
      {
        Sid      = "Bedrock"
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel", "bedrock:Converse"]
        Resource = ["*"]
      },
      {
        Sid      = "AOSSAPI"
        Effect   = "Allow"
        Action   = ["aoss:APIAccessAll"]
        Resource = ["*"]
      },
      {
        Sid      = "Logs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = ["arn:${data.aws_partition.current.partition}:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"]
      }
    ]
  })
}

resource "aws_iam_role" "sfn" {
  name               = "${var.name_prefix}-sfn"
  assume_role_policy = data.aws_iam_policy_document.sfn_assume.json
  tags               = var.tags
}

resource "aws_ecs_cluster" "pipeline" {
  name = "${var.name_prefix}-sec-signals"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
  tags = var.tags
}

locals {
  image_uri = var.container_image != "" ? var.container_image : "${aws_ecr_repository.worker.repository_url}:latest"
  lambda_zip_configured = (
    var.lambda_package_path != "" ? fileexists(var.lambda_package_path) : false
  )
}

resource "aws_ecs_task_definition" "index_emit" {
  family                   = "${var.name_prefix}-index-emit"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.fargate_task.arn
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
  container_definitions = jsonencode([
    {
      name      = "index-emit"
      image     = local.image_uri
      essential = true
      command = [
        "python", "-m", "sec_signals.pipeline.fargate_index_emit_main",
        "--help"
      ]
      environment = [
        { name = "AWS_REGION", value = var.aws_region },
        { name = "SEC_SIGNALS_RAW_BUCKET", value = var.lake_bucket },
        { name = "SEC_SIGNALS_AOSS_ENDPOINT", value = var.aoss_endpoint },
        { name = "SEC_SIGNALS_AOSS_COLLECTION", value = var.aoss_collection_name },
        { name = "SEC_SIGNALS_LLM_MODEL_ID", value = "eu.anthropic.claude-haiku-4-5-20251001-v1:0" },
        { name = "SEC_SIGNALS_EMBED_MODEL_ID", value = "amazon.titan-embed-text-v2:0" },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.pipeline.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "fargate"
        }
      }
    }
  ])
  tags = var.tags
}

resource "aws_iam_role_policy" "sfn" {
  name = "${var.name_prefix}-sfn"
  role = aws_iam_role.sfn.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "RunEcsTask"
        Effect   = "Allow"
        Action   = ["ecs:RunTask"]
        Resource = [aws_ecs_task_definition.index_emit.arn]
      },
      {
        Sid    = "PassRoles"
        Effect = "Allow"
        Action = ["iam:PassRole"]
        Resource = [
          aws_iam_role.ecs_execution.arn,
          aws_iam_role.fargate_task.arn
        ]
      },
      {
        Sid      = "StopDescribe"
        Effect   = "Allow"
        Action   = ["ecs:StopTask", "ecs:DescribeTasks"]
        Resource = ["*"]
      },
      {
        Sid    = "EventsManagedRule"
        Effect = "Allow"
        Action = [
          "events:PutTargets",
          "events:PutRule",
          "events:DescribeRule"
        ]
        Resource = [
          "arn:${data.aws_partition.current.partition}:events:${var.aws_region}:${data.aws_caller_identity.current.account_id}:rule/StepFunctionsGetEventsForECSTaskRule"
        ]
      }
    ]
  })
}

resource "aws_sfn_state_machine" "index_emit" {
  name     = "${var.name_prefix}-index-emit"
  role_arn = aws_iam_role.sfn.arn
  definition = jsonencode({
    Comment = "Primary on-ingest index+emit+warehouse via ECS Fargate"
    StartAt = "SkipSidecars"
    States = {
      SkipSidecars = {
        Type = "Choice"
        Choices = [
          {
            Variable     = "$.key"
            StringMatches = "*/provenance.json"
            Next         = "IgnoredSidecar"
          }
        ]
        Default = "ParseKey"
      }
      IgnoredSidecar = {
        Type   = "Succeed"
        Comment = "Ignore provenance.json object-created events"
      }
      ParseKey = {
        Type = "Pass"
        Parameters = {
          "bucket.$" = "$.bucket"
          "key.$"    = "$.key"
          "parts.$"  = "States.StringSplit($.key, '/')"
        }
        Next = "ExtractIds"
      }
      ExtractIds = {
        Type = "Pass"
        Parameters = {
          "bucket.$"     = "$.bucket"
          "key.$"        = "$.key"
          "cik.$"        = "States.ArrayGetItem($.parts, 2)"
          "accession.$"  = "States.ArrayGetItem($.parts, 3)"
        }
        Next = "RunIndexEmit"
      }
      RunIndexEmit = {
        Type     = "Task"
        Resource = "arn:aws:states:::ecs:runTask.sync"
        Parameters = {
          LaunchType     = "FARGATE"
          Cluster        = aws_ecs_cluster.pipeline.arn
          TaskDefinition = aws_ecs_task_definition.index_emit.arn
          NetworkConfiguration = {
            AwsvpcConfiguration = {
              Subnets        = data.aws_subnets.default.ids
              AssignPublicIp = "ENABLED"
            }
          }
          Overrides = {
            ContainerOverrides = [
              {
                Name = "index-emit"
                "Command.$" = "States.Array('python','-m','sec_signals.pipeline.fargate_index_emit_main','--bucket',$.bucket,'--cik',$.cik,'--accession',$.accession,'--mode','index_emit')"
              }
            ]
          }
        }
        End = true
      }
    }
  })
  tags = var.tags
}

resource "aws_iam_role" "events_to_sfn" {
  name               = "${var.name_prefix}-events-sfn"
  assume_role_policy = data.aws_iam_policy_document.events_assume.json
  tags               = var.tags
}

resource "aws_iam_role_policy" "events_to_sfn" {
  name = "${var.name_prefix}-events-sfn"
  role = aws_iam_role.events_to_sfn.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["states:StartExecution"]
      Resource = [aws_sfn_state_machine.index_emit.arn]
    }]
  })
}

resource "aws_cloudwatch_event_rule" "raw_created" {
  name = "${var.name_prefix}-raw-created"
  event_pattern = jsonencode({
    source      = ["aws.s3"]
    detail-type = ["Object Created"]
    detail = {
      bucket = { name = [var.lake_bucket] }
      object = {
        key = [{ prefix = "raw/edgar/" }]
      }
    }
  })
  tags = var.tags
}

resource "aws_cloudwatch_event_target" "raw_created_sfn" {
  rule      = aws_cloudwatch_event_rule.raw_created.name
  target_id = "IndexEmitStateMachine"
  arn       = aws_sfn_state_machine.index_emit.arn
  role_arn  = aws_iam_role.events_to_sfn.arn
  input_transformer {
    input_paths = {
      bucket = "$.detail.bucket.name"
      key    = "$.detail.object.key"
    }
    input_template = <<-EOT
    {"bucket": <bucket>, "key": <key>}
    EOT
  }
}

resource "random_password" "demo_api_key" {
  count   = var.demo_api_key == "" ? 1 : 0
  length  = 32
  special = false
}

locals {
  demo_api_key = var.demo_api_key != "" ? var.demo_api_key : random_password.demo_api_key[0].result
}

resource "aws_ssm_parameter" "demo_api_key" {
  name        = "/${var.name_prefix}/demo-api-key"
  description = "API key for POST /v1/signals:batchEmit (x-api-key); not a public anonymous API"
  type        = "SecureString"
  value       = local.demo_api_key
  tags        = var.tags
}

data "archive_file" "emit_lambda_stub" {
  type        = "zip"
  source_file = "${path.module}/lambda_stub_handler.py"
  output_path = "${path.module}/.build/emit_lambda_stub.zip"
}

resource "aws_lambda_function" "emit" {
  function_name = "${var.name_prefix}-emit"
  role          = aws_iam_role.emit_lambda.arn
  handler       = local.lambda_zip_configured ? "handlers.lambda_handler" : "lambda_stub_handler.lambda_handler"
  runtime       = "python3.12"
  filename      = local.lambda_zip_configured ? var.lambda_package_path : data.archive_file.emit_lambda_stub.output_path
  source_code_hash = local.lambda_zip_configured ? filebase64sha256(var.lambda_package_path) : data.archive_file.emit_lambda_stub.output_base64sha256
  timeout       = 120
  memory_size   = 1024
  environment {
    variables = {
      SEC_SIGNALS_RAW_BUCKET      = var.lake_bucket
      SEC_SIGNALS_AOSS_ENDPOINT   = var.aoss_endpoint
      SEC_SIGNALS_AOSS_COLLECTION = var.aoss_collection_name
      SEC_SIGNALS_LLM_MODEL_ID    = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
      SEC_SIGNALS_EMBED_MODEL_ID  = "amazon.titan-embed-text-v2:0"
      DEMO_API_KEY                = local.demo_api_key
      DEMO_REQUIRE_API_KEY        = "true"
    }
  }
  tags = var.tags
}

resource "aws_apigatewayv2_api" "emit" {
  name          = "${var.name_prefix}-emit-api"
  protocol_type = "HTTP"
  tags          = var.tags
}

resource "aws_apigatewayv2_integration" "emit" {
  api_id                 = aws_apigatewayv2_api.emit.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.emit.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "health" {
  # Intentionally public liveness probe; no Bedrock/S3 side effects.
  api_id    = aws_apigatewayv2_api.emit.id
  route_key = "GET /v1/health"
  target    = "integrations/${aws_apigatewayv2_integration.emit.id}"
}

resource "aws_apigatewayv2_route" "batch_emit" {
  # Internal demo: require SigV4 (IAM). App layer also enforces DEMO_API_KEY (fail-closed).
  api_id             = aws_apigatewayv2_api.emit.id
  route_key          = "POST /v1/signals:batchEmit"
  target             = "integrations/${aws_apigatewayv2_integration.emit.id}"
  authorization_type = "AWS_IAM"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.emit.id
  name        = "$default"
  auto_deploy = true
  tags        = var.tags
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.emit.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.emit.execution_arn}/*/*"
}

output "state_machine_arn" {
  value = aws_sfn_state_machine.index_emit.arn
}

output "emit_lambda_role_arn" {
  value = aws_iam_role.emit_lambda.arn
}

output "fargate_task_role_arn" {
  value = aws_iam_role.fargate_task.arn
}

output "ecr_repository_url" {
  value = aws_ecr_repository.worker.repository_url
}

output "ecs_cluster_arn" {
  value = aws_ecs_cluster.pipeline.arn
}

output "emit_api_endpoint" {
  value = aws_apigatewayv2_api.emit.api_endpoint
}

output "demo_api_key_ssm_parameter" {
  value       = aws_ssm_parameter.demo_api_key.name
  description = "SSM SecureString holding DEMO_API_KEY for batch emit callers"
}

output "task_definition_arn" {
  value = aws_ecs_task_definition.index_emit.arn
}
