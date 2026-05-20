# ---------------------------------------------------------------
# IAM roles for Pod Identity
# Each backend pod gets its own role scoped to what it needs.
# Pod Identity associations are created in infra-cluster
# (they reference the EKS cluster name).
# ---------------------------------------------------------------

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Trust policy for EKS Pod Identity
data "aws_iam_policy_document" "pod_identity_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole", "sts:TagSession"]
    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}

# ---------------------------------------------------------------
# Data service role
# Needs: S3 read/write on space buckets, DynamoDB read (lookup)
# ---------------------------------------------------------------
resource "aws_iam_role" "data_service" {
  name               = "${local.prefix}-data-service"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_trust.json

  tags = { Name = "${local.prefix}-data-service" }
}

resource "aws_iam_role_policy" "data_service" {
  name = "data-service-policy"
  role = aws_iam_role.data_service.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3SpaceBuckets"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:GetBucketVersioning",
          "s3:PutBucketVersioning",
          "s3:GetBucketLocation",
        ]
        Resource = [
          "arn:aws:s3:::${local.prefix}-space-*",
          "arn:aws:s3:::${local.prefix}-space-*/*",
          "arn:aws:s3:::${local.prefix}-demo-data",
          "arn:aws:s3:::${local.prefix}-demo-data/*",
        ]
      },
      {
        Sid    = "DynamoDBLookup"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:Query",
        ]
        Resource = [
          aws_dynamodb_table.resources.arn,
          "${aws_dynamodb_table.resources.arn}/index/*",
        ]
      },
      {
        Sid    = "GeneratePresignedUrls"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject"]
        Resource = [
          "arn:aws:s3:::${local.prefix}-space-*/*",
        ]
      }
    ]
  })
}

# ---------------------------------------------------------------
# Provisioning service role
# Needs: SQS consume, S3 create buckets, IAM create roles,
#        DynamoDB write (status updates)
# ---------------------------------------------------------------
resource "aws_iam_role" "provisioning_service" {
  name               = "${local.prefix}-provisioning-service"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_trust.json

  tags = { Name = "${local.prefix}-provisioning-service" }
}

resource "aws_iam_role_policy" "provisioning_service" {
  name = "provisioning-service-policy"
  role = aws_iam_role.provisioning_service.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SQSConsume"
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility",
        ]
        Resource = aws_sqs_queue.provisioning.arn
      },
      {
        Sid    = "S3CreateSpaceBuckets"
        Effect = "Allow"
        Action = [
          "s3:CreateBucket",
          "s3:PutBucketPolicy",
          "s3:PutBucketVersioning",
          "s3:PutBucketTagging",
          "s3:PutBucketNotification",
          "s3:PutLifecycleConfiguration",
          "s3:PutEncryptionConfiguration",
          "s3:PutPublicAccessBlock",
        ]
        Resource = "arn:aws:s3:::${local.prefix}-space-*"
      },
      {
        Sid    = "IAMCreateSpaceRoles"
        Effect = "Allow"
        Action = [
          "iam:CreateRole",
          "iam:AttachRolePolicy",
          "iam:PutRolePolicy",
          "iam:TagRole",
          "iam:GetRole",
        ]
        Resource = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${local.prefix}-space-*"
      },
      {
        Sid    = "DynamoDBStatusUpdate"
        Effect = "Allow"
        Action = [
          "dynamodb:UpdateItem",
          "dynamodb:GetItem",
        ]
        Resource = aws_dynamodb_table.resources.arn
      },
      {
        Sid    = "SNSCreateNotifications"
        Effect = "Allow"
        Action = [
          "sns:CreateTopic",
          "sns:SetTopicAttributes",
          "sns:TagResource",
        ]
        Resource = "arn:aws:sns:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:${local.prefix}-space-*"
      }
    ]
  })
}

# ---------------------------------------------------------------
# Usage service role
# Needs: CloudWatch GetMetrics, S3 ListBuckets, DynamoDB write
# ---------------------------------------------------------------
resource "aws_iam_role" "usage_service" {
  name               = "${local.prefix}-usage-service"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_trust.json

  tags = { Name = "${local.prefix}-usage-service" }
}

resource "aws_iam_role_policy" "usage_service" {
  name = "usage-service-policy"
  role = aws_iam_role.usage_service.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchMetrics"
        Effect = "Allow"
        Action = [
          "cloudwatch:GetMetricData",
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:ListMetrics",
        ]
        Resource = "*"
      },
      {
        Sid    = "S3ListBuckets"
        Effect = "Allow"
        Action = [
          "s3:ListAllMyBuckets",
          "s3:GetBucketLocation",
          "s3:ListBucket",
        ]
        Resource = "*"
      },
      {
        Sid    = "DynamoDBWriteUsage"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:GetItem",
          "dynamodb:Query",
        ]
        Resource = [
          aws_dynamodb_table.resources.arn,
          "${aws_dynamodb_table.resources.arn}/index/*",
        ]
      }
    ]
  })
}
