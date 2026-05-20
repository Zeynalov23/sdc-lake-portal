# ---------------------------------------------------------------
# Resources table
# Stores all provisioned spaces, access grants, notifications etc.
# Streams enabled so DynamoDB → SQS → Provisioning service pod
# ---------------------------------------------------------------
resource "aws_dynamodb_table" "resources" {
  name         = "${local.prefix}-resources"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  attribute {
    name = "userId"
    type = "S"
  }

  # GSI for looking up all spaces a user is a member of
  global_secondary_index {
    name            = "userId-index"
    hash_key        = "userId"
    projection_type = "ALL"
  }

  stream_enabled   = true
  stream_view_type = "NEW_IMAGE"

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name = "${local.prefix}-resources"
  }
}
