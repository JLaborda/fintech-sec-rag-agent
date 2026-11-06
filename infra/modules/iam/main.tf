terraform {
  required_version = ">= 1.5.0"
}

# Phase-1 demo IAM lives primarily in modules/compute (task / Lambda / SFN / EventBridge roles).
# This module documents the least-privilege surface area for operators reviewing TF plans.
#
# Required live permissions (attached in compute):
# - S3 lake Get/Put/List on raw + curated prefixes
# - Bedrock InvokeModel + Converse (Haiku 4.5 EU geo + Titan V2)
# - aoss:APIAccessAll (paired with AOSS data-access policy principals)
# - CloudWatch Logs write for Fargate / Lambda
# - states:StartExecution from EventBridge role
# - ecs:RunTask + iam:PassRole from Step Functions role
