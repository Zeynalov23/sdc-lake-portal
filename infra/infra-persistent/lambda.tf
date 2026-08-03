# ---------------------------------------------------------------
# Write Lambda + API Gateway
# Packages the Lambda from local source, deploys to AWS,
# wires up API Gateway with routes and an API key for now
# ---------------------------------------------------------------

# ---------------------------------------------------------------
# Package the Lambda code into a zip
# Terraform re-packages whenever source files change
# ---------------------------------------------------------------
data "archive_file" "write_lambda" {
  type        = "zip"
  source_dir  = "${path.module}/../../backend/write-lambda"
  output_path = "${path.module}/../../backend/write-lambda.zip"
}

# ---------------------------------------------------------------
# IAM role for the Write Lambda
# Only needs DynamoDB PutItem + CloudWatch Logs
# ---------------------------------------------------------------
resource "aws_iam_role" "write_lambda" {
  name = "${local.prefix}-write-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = { Name = "${local.prefix}-write-lambda" }
}

resource "aws_iam_role_policy" "write_lambda" {
  name = "write-lambda-policy"
  role = aws_iam_role.write_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DynamoDBWrite"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query",
        ]
        Resource = [
          aws_dynamodb_table.resources.arn,
          "${aws_dynamodb_table.resources.arn}/index/*",
        ]
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# ---------------------------------------------------------------
# Write Lambda function
# ---------------------------------------------------------------
resource "aws_lambda_function" "write" {
  function_name    = "${local.prefix}-write"
  role             = aws_iam_role.write_lambda.arn
  handler          = "lambda_function.handler"
  runtime          = "python3.12"
  filename         = data.archive_file.write_lambda.output_path
  source_code_hash = data.archive_file.write_lambda.output_base64sha256
  timeout          = 30
  memory_size      = 256

  environment {
    variables = {
      DYNAMODB_TABLE = aws_dynamodb_table.resources.name
      ENVIRONMENT    = var.environment
    }
  }

  tags = { Name = "${local.prefix}-write" }
}

# CloudWatch log group for the Lambda
resource "aws_cloudwatch_log_group" "write_lambda" {
  name              = "/aws/lambda/${aws_lambda_function.write.function_name}"
  retention_in_days = 14
}

# ---------------------------------------------------------------
# API Gateway (REST)
# ---------------------------------------------------------------
resource "aws_api_gateway_rest_api" "main" {
  name        = "${local.prefix}-api"
  description = "SDC Lake Portal control plane API"

  tags = { Name = "${local.prefix}-api" }
}

# ---------------------------------------------------------------
# API key for now — replaced by Cognito authorizer later
# ---------------------------------------------------------------
resource "aws_api_gateway_api_key" "main" {
  name = "${local.prefix}-api-key"
}

resource "aws_api_gateway_usage_plan" "main" {
  name = "${local.prefix}-usage-plan"

  api_stages {
    api_id = aws_api_gateway_rest_api.main.id
    stage  = aws_api_gateway_stage.main.stage_name
  }
}

resource "aws_api_gateway_usage_plan_key" "main" {
  key_id        = aws_api_gateway_api_key.main.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.main.id
}

# ---------------------------------------------------------------
# Routes — /spaces, /access, /notifications
# Each follows the same pattern:
# resource → method → lambda integration → method response
# ---------------------------------------------------------------
locals {
  routes = {
    spaces        = "spaces"
    access        = "access"
    notifications = "notifications"
  }
}

resource "aws_api_gateway_resource" "routes" {
  for_each    = local.routes
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = each.value
}

resource "aws_api_gateway_method" "post" {
  for_each         = local.routes
  rest_api_id      = aws_api_gateway_rest_api.main.id
  resource_id      = aws_api_gateway_resource.routes[each.key].id
  http_method      = "POST"
  authorization    = "NONE"
  api_key_required = true
}

resource "aws_api_gateway_integration" "lambda" {
  for_each                = local.routes
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.routes[each.key].id
  http_method             = aws_api_gateway_method.post[each.key].http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.write.invoke_arn
}

# ---------------------------------------------------------------
# Lambda permission — allow API Gateway to invoke the Lambda
# ---------------------------------------------------------------
resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.write.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"
}

# ---------------------------------------------------------------
# Deployment and stage
# ---------------------------------------------------------------
resource "aws_api_gateway_deployment" "main" {
  rest_api_id = aws_api_gateway_rest_api.main.id

  # Redeploy whenever routes or integrations change
  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.routes,
      aws_api_gateway_method.post,
      aws_api_gateway_integration.lambda,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [aws_api_gateway_integration.lambda]
}

resource "aws_api_gateway_stage" "main" {
  deployment_id = aws_api_gateway_deployment.main.id
  rest_api_id   = aws_api_gateway_rest_api.main.id
  stage_name    = var.environment

  tags = { Name = "${local.prefix}-api-stage" }
}
