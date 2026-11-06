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

variable "tags" {
  type    = map(string)
  default = {}
}

variable "data_access_principal_arns" {
  type        = list(string)
  description = "IAM principal ARNs granted AOSS data-plane access (Fargate task role, Lambda, operators)."
  default     = []
}

variable "allow_public_network" {
  type        = bool
  description = "Demo default: public network access. Tighten to VPC endpoints for production."
  default     = true
}

data "aws_caller_identity" "current" {}

locals {
  collection_name = "${var.name_prefix}-chunks"
  principals = length(var.data_access_principal_arns) > 0 ? var.data_access_principal_arns : [
    data.aws_caller_identity.current.arn
  ]
}

resource "aws_opensearchserverless_security_policy" "encryption" {
  name = "${var.name_prefix}-enc"
  type = "encryption"
  policy = jsonencode({
    Rules = [{
      ResourceType = "collection"
      Resource     = ["collection/${local.collection_name}"]
    }]
    AWSOwnedKey = true
  })
}

resource "aws_opensearchserverless_security_policy" "network" {
  name = "${var.name_prefix}-net"
  type = "network"
  policy = jsonencode([
    {
      Description     = "Network access for ${local.collection_name}"
      AllowFromPublic = var.allow_public_network
      Rules = [
        {
          ResourceType = "collection"
          Resource     = ["collection/${local.collection_name}"]
        },
        {
          ResourceType = "dashboard"
          Resource     = ["collection/${local.collection_name}"]
        }
      ]
    }
  ])
}

resource "aws_opensearchserverless_access_policy" "data" {
  name = "${var.name_prefix}-data"
  type = "data"
  policy = jsonencode([
    {
      Rules = [
        {
          ResourceType = "index"
          Resource     = ["index/${local.collection_name}/*"]
          Permission = [
            "aoss:CreateIndex",
            "aoss:DescribeIndex",
            "aoss:ReadDocument",
            "aoss:WriteDocument",
            "aoss:UpdateIndex",
            "aoss:DeleteIndex"
          ]
        },
        {
          ResourceType = "collection"
          Resource     = ["collection/${local.collection_name}"]
          Permission = [
            "aoss:CreateCollectionItems",
            "aoss:DescribeCollectionItems",
            "aoss:UpdateCollectionItems"
          ]
        }
      ]
      Principal = local.principals
    }
  ])
}

resource "aws_opensearchserverless_collection" "chunks" {
  name = local.collection_name
  type = "VECTORSEARCH"
  tags = var.tags
  depends_on = [
    aws_opensearchserverless_security_policy.encryption,
    aws_opensearchserverless_security_policy.network,
  ]
}

output "collection_name" {
  value = aws_opensearchserverless_collection.chunks.name
}

output "collection_endpoint" {
  value = aws_opensearchserverless_collection.chunks.collection_endpoint
}

output "collection_arn" {
  value = aws_opensearchserverless_collection.chunks.arn
}
