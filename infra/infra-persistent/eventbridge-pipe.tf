# ---------------------------------------------------------------
# EventBridge Pipe: DynamoDB Streams → SQS
# Replaces the old fan-out Lambda pattern.
# Filters for INSERT events only (new space/access/notification requests).
# No code to maintain — just config.
# ---------------------------------------------------------------

# IAM role for the pipe
resource "aws_iam_role" "streams_pipe" {
  name = "${local.prefix}-streams-pipe"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "pipes.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = { Name = "${local.prefix}-streams-pipe" }
}

resource "aws_iam_role_policy" "streams_pipe" {
  name = "streams-pipe-policy"
  role = aws_iam_role.streams_pipe.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadDynamoDBStreams"
        Effect = "Allow"
        Action = [
          "dynamodb:GetRecords",
          "dynamodb:GetShardIterator",
          "dynamodb:DescribeStream",
          "dynamodb:ListStreams",
        ]
        Resource = aws_dynamodb_table.resources.stream_arn
      },
      {
        Sid    = "SendToSQS"
        Effect = "Allow"
        Action = ["sqs:SendMessage"]
        Resource = aws_sqs_queue.provisioning.arn
      }
    ]
  })
}

# The pipe itself
resource "aws_pipes_pipe" "dynamo_to_sqs" {
  name     = "${local.prefix}-dynamo-to-sqs"
  role_arn = aws_iam_role.streams_pipe.arn

  source = aws_dynamodb_table.resources.stream_arn
  source_parameters {
    dynamodb_stream_parameters {
      starting_position    = "LATEST"
      batch_size           = 1      # process one record at a time
      maximum_retry_attempts = 3
    }

    # Only forward INSERT events — ignore MODIFY and REMOVE
    filter_criteria {
      filter {
        pattern = jsonencode({
          eventName = ["INSERT"]
        })
      }
    }
  }

  target = aws_sqs_queue.provisioning.arn

  tags = { Name = "${local.prefix}-dynamo-to-sqs" }
}

# ---------------------------------------------------------------
# Add Cognito Identity Pool permissions to provisioning service role
# The provisioning service needs to update Identity Pool role mappings
# when new spaces are created
# ---------------------------------------------------------------
resource "aws_iam_role_policy" "provisioning_cognito" {
  name = "provisioning-cognito-policy"
  role = "${local.prefix}-provisioning-service"  # role created in iam.tf

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "UpdateIdentityPoolRoles"
        Effect = "Allow"
        Action = [
          "cognito-identity:GetIdentityPoolRoles",
          "cognito-identity:SetIdentityPoolRoles",
        ]
        Resource = "arn:aws:cognito-identity:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:identitypool/${aws_cognito_identity_pool.main.id}"
      }
    ]
  })
}
