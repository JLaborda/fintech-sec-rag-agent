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

resource "aws_s3_bucket" "lake" {
  bucket = "${var.name_prefix}-sec-signals-lake"
  tags   = var.tags
}

resource "aws_s3_bucket_versioning" "lake" {
  bucket = aws_s3_bucket.lake.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_glue_catalog_database" "sec_signals" {
  name = "sec_signals"
}

resource "aws_glue_catalog_table" "curated_signals" {
  name          = "curated_signals"
  database_name = aws_glue_catalog_database.sec_signals.name
  table_type    = "EXTERNAL_TABLE"

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.lake.bucket}/curated/signals/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"
    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }
    columns {
      name = "cik"
      type = "string"
    }
    columns {
      name = "accession_number"
      type = "string"
    }
    columns {
      name = "form"
      type = "string"
    }
    columns {
      name = "model_or_pipeline_version"
      type = "string"
    }
    columns {
      name = "emitted_at"
      type = "string"
    }
    columns {
      name = "factor_id"
      type = "string"
    }
    columns {
      name = "status"
      type = "string"
    }
    columns {
      name = "polarity"
      type = "double"
    }
    columns {
      name = "conviction"
      type = "double"
    }
    columns {
      name = "citation_section"
      type = "string"
    }
    columns {
      name = "citation_item"
      type = "string"
    }
    columns {
      name = "citation_quote"
      type = "string"
    }
    columns {
      name = "reasoning"
      type = "string"
    }
    columns {
      name = "disclaimer"
      type = "string"
    }
  }

  partition_keys {
    name = "factor_schema_version"
    type = "string"
  }
  partition_keys {
    name = "ticker"
    type = "string"
  }
  partition_keys {
    name = "filing_date"
    type = "string"
  }
}

resource "aws_athena_workgroup" "sec_signals" {
  name = "${var.name_prefix}-sec-signals"

  configuration {
    enforce_workgroup_configuration = true
    result_configuration {
      output_location = "s3://${aws_s3_bucket.lake.bucket}/athena-results/"
    }
  }
}

output "bucket_name" {
  value = aws_s3_bucket.lake.bucket
}

output "glue_database" {
  value = aws_glue_catalog_database.sec_signals.name
}

output "glue_table" {
  value = aws_glue_catalog_table.curated_signals.name
}

output "athena_workgroup" {
  value = aws_athena_workgroup.sec_signals.name
}
