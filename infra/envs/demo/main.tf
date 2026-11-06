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
  }
}

variable "aws_region" {
  type    = string
  default = "eu-west-1"
}

variable "name_prefix" {
  type    = string
  default = "demo"
}

variable "container_image" {
  type    = string
  default = ""
}

variable "lambda_package_path" {
  type        = string
  description = "Absolute or repo-relative path to emit Lambda zip from scripts/package_emit_lambda.sh"
  default     = ""
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  tags = {
    Project = "fintech-sec-rag-agent"
    Phase   = "1"
  }
  # Construct role ARNs by convention to avoid compute ↔ vector cycles.
  fargate_task_role_arn = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:role/${var.name_prefix}-fargate-task"
  emit_lambda_role_arn  = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:role/${var.name_prefix}-emit-lambda"
}

module "lake" {
  source      = "../../modules/lake"
  name_prefix = var.name_prefix
  tags        = local.tags
}

module "vector" {
  source                     = "../../modules/vector"
  name_prefix                = var.name_prefix
  tags                       = local.tags
  data_access_principal_arns = [local.fargate_task_role_arn, local.emit_lambda_role_arn]
  allow_public_network       = true
}

module "compute" {
  source               = "../../modules/compute"
  name_prefix          = var.name_prefix
  lake_bucket          = module.lake.bucket_name
  lake_bucket_arn      = module.lake.bucket_arn
  aoss_collection_name = module.vector.collection_name
  aoss_endpoint        = coalesce(module.vector.collection_endpoint, "")
  aws_region           = var.aws_region
  container_image      = var.container_image
  lambda_package_path  = var.lambda_package_path
  tags                 = local.tags
}

output "bucket" {
  value = module.lake.bucket_name
}

output "glue_database" {
  value = module.lake.glue_database
}

output "glue_table" {
  value = module.lake.glue_table
}

output "athena_workgroup" {
  value = module.lake.athena_workgroup
}

output "aoss_endpoint" {
  value = module.vector.collection_endpoint
}

output "state_machine_arn" {
  value = module.compute.state_machine_arn
}

output "ecr_repository_url" {
  value = module.compute.ecr_repository_url
}

output "emit_api_endpoint" {
  value = module.compute.emit_api_endpoint
}

output "pipeline_version" {
  value = "0.1.0"
}
