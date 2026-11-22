# ---------------------------------------------------------------
# GitHub Actions identity
#
# No access keys. GitHub mints a short-lived OIDC token for each workflow
# run, AWS validates it against this provider, and the run assumes the role
# below. Nothing long-lived exists to leak, and there is no secret to rotate
# - the only thing stored in GitHub is the role ARN, which is not sensitive.
# ---------------------------------------------------------------

# The thumbprint is read from the live certificate rather than hardcoded.
# AWS no longer verifies it for this provider, but the argument is still
# required, and a pasted value silently rots when GitHub rotates its chain.
data "tls_certificate" "github" {
  url = "https://token.actions.githubusercontent.com/.well-known/openid-configuration"
}

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.github.certificates[0].sha1_fingerprint]

  tags = {
    Name = "${local.prefix}-github-actions"
  }
}

data "aws_iam_policy_document" "github_actions_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # Scoped to pushes on main, not to the repository as a whole. With
    # `repo:owner/name:*` any branch could assume this role, which means
    # anyone who can open a branch can push an image to the registry the
    # cluster pulls from. Narrow it further with an environment claim if
    # the workflow ever needs to deploy rather than only build.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repository}:ref:refs/heads/main"]
    }
  }
}

data "aws_iam_policy_document" "github_actions_ecr" {
  # GetAuthorizationToken is account-wide by design: there is no resource to
  # scope it to. It only returns a token; pushing still requires the second
  # statement.
  statement {
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
      "ecr:PutImage",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]
    # Named repositories only. A wildcard here would let a compromised
    # workflow push to any repository in the account.
    resources = [for r in aws_ecr_repository.services : r.arn]
  }
}

resource "aws_iam_role" "github_actions" {
  name               = "${local.prefix}-github-actions"
  assume_role_policy = data.aws_iam_policy_document.github_actions_trust.json

  tags = {
    Name = "${local.prefix}-github-actions"
  }
}

resource "aws_iam_role_policy" "github_actions_ecr" {
  name   = "ecr-push"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.github_actions_ecr.json
}
