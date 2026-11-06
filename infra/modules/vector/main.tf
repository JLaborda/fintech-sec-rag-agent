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

# OpenSearch Serverless collection scaffold (RAG only).
resource "aws_opensearchserverless_security_policy" "encryption" {
  name = "${var.name_prefix}-enc"
  type = "encryption"
  policy = jsonencode({
    Rules = [{
      ResourceType = "collection"
      Resource     = ["collection/${var.name_prefix}-chunks"]
    }]
    AWSOwnedKey = true
  })
}

resource "aws_opensearchserverless_collection" "chunks" {
  name = "${var.name_prefix}-chunks"
  type = "VECTORSEARCH"
  tags = var.tags
  depends_on = [aws_opensearchserverless_security_policy.encryption]
}

output "collection_name" {
  value = aws_opensearchserverless_collection.chunks.name
}

output "collection_endpoint" {
  value = aws_opensearchserverless_collection.chunks.collection_endpoint
}
