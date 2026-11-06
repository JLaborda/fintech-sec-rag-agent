terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

variable "name_prefix" {
  type = string
}

variable "lake_bucket" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

# Secondary re-emit Lambda placeholder package expects zip uploaded separately.
resource "aws_iam_role" "emit_lambda" {
  name = "${var.name_prefix}-emit-lambda"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
  tags = var.tags
}

resource "aws_iam_role" "fargate_task" {
  name = "${var.name_prefix}-fargate-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
  tags = var.tags
}

resource "aws_cloudwatch_log_group" "pipeline" {
  name              = "/sec-signals/${var.name_prefix}"
  retention_in_days = 14
  tags              = var.tags
}

resource "aws_sfn_state_machine" "index_emit" {
  name     = "${var.name_prefix}-index-emit"
  role_arn = aws_iam_role.fargate_task.arn
  definition = jsonencode({
    Comment = "Primary on-ingest index+emit+warehouse orchestration scaffold"
    StartAt = "IndexEmit"
    States = {
      IndexEmit = {
        Type   = "Pass"
        Result = "index_emit"
        End    = true
      }
    }
  })
  tags = var.tags
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
