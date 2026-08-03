# ---------------------------------------------------------------
# Read Entra ID credentials from Secrets Manager
# Values stored manually via AWS CLI before applying this
# ---------------------------------------------------------------
data "aws_secretsmanager_secret_version" "app_config" {
  secret_id = "${local.prefix}/app-config"
}

locals {
  app_config = jsondecode(data.aws_secretsmanager_secret_version.app_config.secret_string)
}

# ---------------------------------------------------------------
# Cognito User Pool
# Handles authentication — federates with Entra ID via OIDC
# Issues Cognito JWTs after successful Entra login
# ---------------------------------------------------------------
resource "aws_cognito_user_pool" "main" {
  name = "${local.prefix}-user-pool"

  # Users sign in with email
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  # Password policy — relaxed since users sign in via Entra
  # not via Cognito native passwords
  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = false
    temporary_password_validity_days = 7
  }

  # Custom attributes we need for space membership
  schema {
    name                     = "entra_oid"
    attribute_data_type      = "String"
    mutable                  = true
    required                 = false
    string_attribute_constraints {
      min_length = 0
      max_length = 256
    }
  }

  tags = {
    Name = "${local.prefix}-user-pool"
  }
}

# ---------------------------------------------------------------
# Entra ID as OIDC identity provider in the User Pool
# ---------------------------------------------------------------
resource "aws_cognito_identity_provider" "entra" {
  user_pool_id  = aws_cognito_user_pool.main.id
  provider_name = "EntraID"
  provider_type = "OIDC"

  provider_details = {
    client_id                = local.app_config.entra_client_id
    client_secret            = local.app_config.entra_client_secret
    attributes_request_method = "GET"
    oidc_issuer              = "https://login.microsoftonline.com/${local.app_config.entra_tenant_id}/v2.0"
    authorize_scopes         = "openid email profile"
  }

  # Map Entra claims to Cognito user attributes
  attribute_mapping = {
    email    = "email"
    username = "sub"
    "custom:entra_oid" = "oid"
  }
}

# ---------------------------------------------------------------
# User Pool Client
# Used by Next.js frontend to initiate the login flow
# ---------------------------------------------------------------
resource "aws_cognito_user_pool_client" "frontend" {
  name         = "${local.prefix}-frontend-client"
  user_pool_id = aws_cognito_user_pool.main.id

  # Enable hosted UI for Entra federation redirect
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]

  # Supported identity providers
  supported_identity_providers = ["EntraID"]

  # Callback URLs — update with real domain once you have one
  # For local dev: http://localhost:3000/api/auth/callback/cognito
  callback_urls = [
    "http://localhost:3000/api/auth/callback/cognito",
  ]

  logout_urls = [
    "http://localhost:3000",
  ]

  # Token validity
  access_token_validity  = 60   # 1 hour in minutes
  id_token_validity      = 60
  refresh_token_validity = 30   # 30 days

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }

  # Don't generate a client secret for public clients (browser apps)
  generate_secret = false

  explicit_auth_flows = [
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]
}

# ---------------------------------------------------------------
# User Pool Domain
# Required for the hosted UI (Entra redirect back to Cognito)
# ---------------------------------------------------------------
resource "aws_cognito_user_pool_domain" "main" {
  domain       = "${local.prefix}-auth"
  user_pool_id = aws_cognito_user_pool.main.id
}

# ---------------------------------------------------------------
# Cognito Identity Pool
# Exchanges Cognito JWTs for temporary AWS credentials
# Maps spaceId + role claims to specific IAM role ARNs
# ---------------------------------------------------------------
resource "aws_cognito_identity_pool" "main" {
  identity_pool_name               = "${local.prefix}-identity-pool"
  allow_unauthenticated_identities = false

  cognito_identity_providers {
    client_id               = aws_cognito_user_pool_client.frontend.id
    provider_name           = aws_cognito_user_pool.main.endpoint
    server_side_token_check = true
  }

  tags = {
    Name = "${local.prefix}-identity-pool"
  }
}

# ---------------------------------------------------------------
# IAM role for Identity Pool authenticated users
# This is the base role — actual space roles are assumed
# via role mapping rules below
# ---------------------------------------------------------------
data "aws_iam_policy_document" "identity_pool_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity", "sts:TagSession"]
    principals {
      type        = "Federated"
      identifiers = ["cognito-identity.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "cognito-identity.amazonaws.com:aud"
      values   = [aws_cognito_identity_pool.main.id]
    }
    condition {
      test     = "ForAnyValue:StringLike"
      variable = "cognito-identity.amazonaws.com:amr"
      values   = ["authenticated"]
    }
  }
}

# Base authenticated role (fallback — should rarely be used)
resource "aws_iam_role" "identity_pool_authenticated" {
  name               = "${local.prefix}-identity-pool-authenticated"
  assume_role_policy = data.aws_iam_policy_document.identity_pool_trust.json

  tags = { Name = "${local.prefix}-identity-pool-authenticated" }
}

resource "aws_iam_role_policy" "identity_pool_authenticated" {
  name = "identity-pool-base-policy"
  role = aws_iam_role.identity_pool_authenticated.id

  # Base role has no permissions — forces use of space-specific roles
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Deny"
        Action   = "*"
        Resource = "*"
      }
    ]
  })
}

# ---------------------------------------------------------------
# Identity Pool role attachment
# Role mapping rules are defined per space when spaces are
# provisioned — they're not static here.
# The provisioning service updates these rules dynamically
# when a new space is created.
# ---------------------------------------------------------------
resource "aws_cognito_identity_pool_roles_attachment" "main" {
  identity_pool_id = aws_cognito_identity_pool.main.id

  roles = {
    authenticated = aws_iam_role.identity_pool_authenticated.arn
  }

  # Role mapping: spaceId + role claim → specific IAM role
  # These are seeded with a placeholder — provisioning service
  # adds real mappings when spaces are created
  role_mapping {
    identity_provider         = "${aws_cognito_user_pool.main.endpoint}:${aws_cognito_user_pool_client.frontend.id}"
    ambiguous_role_resolution = "Deny"
    type                      = "Rules"

    mapping_rule {
      claim      = "custom:spaceId"
      match_type = "Equals"
      value      = "placeholder"
      role_arn   = aws_iam_role.identity_pool_authenticated.arn
    }
  }
}
