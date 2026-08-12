# ---------------------------------------------------------------
# Provisioning queue
# The EventBridge Pipe reads the DynamoDB stream and puts messages here.
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

# No queue policy: the EventBridge Pipe sends with its own IAM role, and for
# SQS an identity-based policy is sufficient within the same account. The old
# policy granted SendMessage to lambda.amazonaws.com for the fan-out Lambda
# that no longer exists.
