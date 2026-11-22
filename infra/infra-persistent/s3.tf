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

# ---------------------------------------------------------------
# Loki chunk storage
#
# Lives here, not in infra-cluster, for the reason in ADR 008: it has to
# outlive the cluster. Loki itself is disposable and rebuilt with everything
# else; its chunks are the only part worth keeping, and they are the reason
# log history survives a teardown at all.
# ---------------------------------------------------------------
resource "aws_s3_bucket" "loki" {
  bucket = "${local.prefix}-loki"

  tags = {
    Name = "${local.prefix}-loki"
  }
}

resource "aws_s3_bucket_public_access_block" "loki" {
  bucket                  = aws_s3_bucket.loki.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "loki" {
  bucket = aws_s3_bucket.loki.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# No versioning, deliberately. Chunks are written once and never modified,
# so versions would only ever be a second copy of an immutable object.
resource "aws_s3_bucket_lifecycle_configuration" "loki" {
  bucket = aws_s3_bucket.loki.id

  rule {
    id     = "expire-chunks"
    status = "Enabled"

    filter {}

    # Log retention is a cost decision and this is where it is actually
    # enforced. Loki's own retention config can disagree with this; the
    # bucket wins, because it is what deletes the bytes.
    expiration {
      days = 30
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}
