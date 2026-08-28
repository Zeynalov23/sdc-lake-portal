output "dynamodb_table_name" {
  value = aws_dynamodb_table.resources.name
}

output "dynamodb_table_arn" {
  value = aws_dynamodb_table.resources.arn
}

output "dynamodb_stream_arn" {
  value = aws_dynamodb_table.resources.stream_arn
}

output "sqs_queue_url" {
  value = aws_sqs_queue.provisioning.url
}

output "sqs_queue_arn" {
  value = aws_sqs_queue.provisioning.arn
}

output "ecr_repository_urls" {
  value = { for k, v in aws_ecr_repository.services : k => v.repository_url }
}

output "iam_role_data_service_arn" {
  value = aws_iam_role.data_service.arn
}

output "iam_role_provisioning_service_arn" {
  value = aws_iam_role.provisioning_service.arn
}

output "demo_data_bucket" {
  value = aws_s3_bucket.demo_data.bucket
}

output "cognito_user_pool_id" {
  value = aws_cognito_user_pool.main.id
}

output "cognito_user_pool_client_id" {
  value = aws_cognito_user_pool_client.frontend.id
}

output "cognito_identity_pool_id" {
  value = aws_cognito_identity_pool.main.id
}

output "cognito_user_pool_endpoint" {
  value = aws_cognito_user_pool.main.endpoint
}

output "cognito_domain" {
  value = aws_cognito_user_pool_domain.main.domain
}
# Add these four as NS records at the registrar, with host set to the
# subdomain label (e.g. "sdc-lake"). Until that is done, Route 53 is not
# authoritative and certificate validation cannot complete.
output "dns_zone_name_servers" {
  value = aws_route53_zone.platform.name_servers
}

output "dns_zone_id" {
  value = aws_route53_zone.platform.zone_id
}

output "dns_zone_name" {
  value = aws_route53_zone.platform.name
}

output "acm_certificate_arn" {
  # Taken from the validation resource rather than the certificate, so that
  # anything referencing it waits until the certificate is actually issued.
  value = aws_acm_certificate_validation.platform.certificate_arn
}
