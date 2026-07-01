output "ecr_repository_url" {
  description = "Backend ECR repository URL."
  value       = aws_ecr_repository.backend.repository_url
}

output "api_url" {
  description = "Public API base URL."
  value       = "https://${var.api_domain_name}"
}

output "websocket_url" {
  description = "Public Twilio ConversationRelay WebSocket URL."
  value       = "wss://${var.ws_domain_name}/twilio/conversation"
}

output "alb_dns_name" {
  description = "Backend ALB DNS name."
  value       = aws_lb.api.dns_name
}

output "api_service_name" {
  description = "ECS API service name."
  value       = aws_ecs_service.api.name
}

output "worker_service_name" {
  description = "ECS worker service name."
  value       = aws_ecs_service.worker.name
}

output "migration_task_definition_arn" {
  description = "One-off Alembic migration task definition ARN."
  value       = aws_ecs_task_definition.migration.arn
}

output "ecs_tasks_security_group_id" {
  description = "Security group ID for API, worker, and migration Fargate tasks."
  value       = aws_security_group.ecs_tasks.id
}

output "upload_bucket_name" {
  description = "S3 bucket for uploaded appliance images."
  value       = aws_s3_bucket.uploads.bucket
}

output "vision_queue_url" {
  description = "SQS queue URL for vision jobs."
  value       = aws_sqs_queue.vision.url
}

output "vision_dlq_url" {
  description = "SQS dead-letter queue URL for failed vision jobs."
  value       = aws_sqs_queue.vision_dlq.url
}

output "database_endpoint" {
  description = "Aurora writer endpoint."
  value       = aws_rds_cluster.database.endpoint
}

output "openai_api_key_secret_arn" {
  description = "Secrets Manager ARN used for the OpenAI API key."
  value       = local.openai_api_key_secret_arn
}

output "twilio_auth_token_secret_arn" {
  description = "Secrets Manager ARN used for the Twilio auth token."
  value       = local.twilio_auth_token_secret_arn
}

output "ses_identity_arn" {
  description = "SES identity ARN for upload-link email."
  value       = aws_ses_domain_identity.email.arn
}
