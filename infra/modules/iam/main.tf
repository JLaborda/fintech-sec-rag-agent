terraform {
  required_version = ">= 1.5.0"
}

# Shared IAM scaffolding lives alongside compute roles for Phase-1 demo.
# Expand least-privilege Bedrock/S3/AOSS/Glue policies during deploy hardening.
