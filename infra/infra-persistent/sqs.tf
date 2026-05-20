# ---------------------------------------------------------------
# Provisioning queue
# DynamoDB Streams fan-out Lambda puts messages here.
# Provisioning service pod consumes from this queue.
# ---------------------------------------------------------------
resource "aws_sqs_queue" "provisioning_dlq" {
  name                      = "${local.prefix}-provisioning-dlq"
  message_retention_seconds = 1209600 # 14 days

  tags = {
    Name = "${local.prefix}-provisioning-dlq"
  }
}

resource "aws_sqs_queue" "provisioning" {
  name                       = "${local.prefix}-provisioning"
  visibility_timeout_seconds = 300 # 5 min — enough for slow AWS SDK calls
  message_retention_seconds  = 86400 # 1 day

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.provisioning_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name = "${local.prefix}-provisioning"
  }
}

# Allow DynamoDB Streams Lambda to send to SQS
resource "aws_sqs_queue_policy" "provisioning" {
  queue_url = aws_sqs_queue.provisioning.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowLambdaSend"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action   = "sqs:SendMessage"
        Resource = aws_sqs_queue.provisioning.arn
      }
    ]
  })
}
