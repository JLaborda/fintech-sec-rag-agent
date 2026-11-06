terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
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

provider "aws" {
  region = var.aws_region
}

locals {
  tags = {
    Project = "fintech-sec-rag-agent"
    Phase   = "1"
  }
}

module "lake" {
  source      = "../../modules/lake"
  name_prefix = var.name_prefix
  tags        = local.tags
}

module "vector" {
  source      = "../../modules/vector"
  name_prefix = var.name_prefix
  tags        = local.tags
}

module "compute" {
  source      = "../../modules/compute"
  name_prefix = var.name_prefix
  lake_bucket = module.lake.bucket_name
  tags        = local.tags
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

output "pipeline_version" {
  value = "0.1.0"
}
