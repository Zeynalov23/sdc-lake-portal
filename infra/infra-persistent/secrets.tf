# ---------------------------------------------------------------
# Secrets Manager
# Placeholder secrets — values filled manually after apply
# ---------------------------------------------------------------
resource "aws_secretsmanager_secret" "app_config" {
  name                    = "${local.prefix}/app-config"
  description             = "General app config (region, table names, queue URLs)"
  recovery_window_in_days = 0

  tags = { Name = "${local.prefix}/app-config" }
}

# Seed the app-config secret with non-sensitive config values
resource "aws_secretsmanager_secret_version" "app_config" {
  secret_id = aws_secretsmanager_secret.app_config.id

  secret_string = jsonencode({
    aws_region         = data.aws_region.current.name
    dynamodb_table     = aws_dynamodb_table.resources.name
    sqs_queue_url      = aws_sqs_queue.provisioning.url
    s3_demo_bucket     = aws_s3_bucket.demo_data.bucket
    environment        = var.environment
  })
}
