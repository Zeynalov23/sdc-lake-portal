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

output "iam_role_usage_service_arn" {
  value = aws_iam_role.usage_service.arn
}

output "demo_data_bucket" {
  value = aws_s3_bucket.demo_data.bucket
}
