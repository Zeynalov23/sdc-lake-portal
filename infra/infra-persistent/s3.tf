# ---------------------------------------------------------------
# Terraform remote state bucket
# Bootstrap: create this manually before the S3 backend is used
# ---------------------------------------------------------------

# ---------------------------------------------------------------
# Demo data bucket (seed bucket for mock files)
# Real space buckets are created dynamically by provisioning svc
# ---------------------------------------------------------------
resource "aws_s3_bucket" "demo_data" {
  bucket = "${local.prefix}-demo-data"

  tags = {
    Name = "${local.prefix}-demo-data"
  }
}

resource "aws_s3_bucket_versioning" "demo_data" {
  bucket = aws_s3_bucket.demo_data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "demo_data" {
  bucket                  = aws_s3_bucket.demo_data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
