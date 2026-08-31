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
        # The data service is now the write path too: the write-lambda and
        # API Gateway are gone, so space creation and member management go
        # through this role. TransactWriteItems needs PutItem and UpdateItem
        # on the table, not a separate action.
        Sid    = "DynamoDBAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
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
          "s3:PutBucketCORS",
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
        # Least privilege follows the code: the per-space IAM roles, S3
        # access points and SNS topics are gone, so those grants go too.
        Sid    = "DynamoDBStatusUpdate"
        Effect = "Allow"
        Action = [
          "dynamodb:UpdateItem",
          "dynamodb:GetItem",
        ]
        Resource = aws_dynamodb_table.resources.arn
      }
    ]
  })
}

# ---------------------------------------------------------------
# ExternalDNS role
# Needs: write records in the platform hosted zone, and list zones to find it.
# ---------------------------------------------------------------
resource "aws_iam_role" "external_dns" {
  name               = "${local.prefix}-external-dns"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_trust.json

  tags = { Name = "${local.prefix}-external-dns" }
}

resource "aws_iam_role_policy" "external_dns" {
  name = "external-dns-policy"
  role = aws_iam_role.external_dns.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # Scoped to the platform zone. ExternalDNS can create and delete
        # records here and nowhere else, so a misconfigured domain filter
        # cannot touch another zone in the account.
        Sid      = "ChangeRecordsInPlatformZone"
        Effect   = "Allow"
        Action   = ["route53:ChangeResourceRecordSets"]
        Resource = aws_route53_zone.platform.arn
      },
      {
        # These two do not support resource-level permissions - Route 53
        # requires "*" - so they are read-only by necessity rather than
        # choice. Listing zones is how ExternalDNS resolves the domain
        # filter to a zone id at startup.
        Sid    = "DiscoverZones"
        Effect = "Allow"
        Action = [
          "route53:ListHostedZones",
          "route53:ListResourceRecordSets",
          "route53:ListTagsForResource",
        ]
        Resource = "*"
      },
    ]
  })
}
