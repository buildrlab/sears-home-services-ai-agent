locals {
  name_prefix        = "${var.project_name}-${var.environment}"
  upload_bucket_name = coalesce(var.upload_bucket_name, "${local.name_prefix}-uploads-${var.workload_account_id}")
  backend_image      = "${aws_ecr_repository.backend.repository_url}:${var.backend_image_tag}"

  openai_api_key_secret_arn = coalesce(
    var.openai_api_key_secret_arn,
    one(aws_secretsmanager_secret.openai_api_key[*].arn),
  )
  twilio_auth_token_secret_arn = coalesce(
    var.twilio_auth_token_secret_arn,
    one(aws_secretsmanager_secret.twilio_auth_token[*].arn),
  )
  database_password_secret_value_from = "${aws_rds_cluster.database.master_user_secret[0].secret_arn}:password::"

  application_environment = [
    for name, value in {
      AWS_REGION                           = var.aws_region
      CORS_ALLOWED_ORIGINS                 = join(",", var.allowed_cors_origins)
      DATABASE_HOST                        = aws_rds_cluster.database.endpoint
      DATABASE_NAME                        = var.database_name
      DATABASE_PORT                        = "5432"
      DATABASE_USER                        = var.database_master_username
      EMAIL_DELIVERY_MODE                  = "ses"
      EMAIL_FROM_ADDRESS                   = var.email_from_address
      ENVIRONMENT                          = var.environment
      OPENAI_MODEL                         = var.openai_model
      OPENAI_REASONING_EFFORT              = "low"
      OPENAI_VERBOSITY                     = "low"
      OPENAI_VISION_MODEL                  = var.openai_vision_model
      PUBLIC_BASE_URL                      = "https://${var.api_domain_name}"
      S3_PRESIGN_EXPIRES_SECONDS           = "900"
      S3_UPLOAD_BUCKET                     = aws_s3_bucket.uploads.bucket
      SQS_VISION_QUEUE_URL                 = aws_sqs_queue.vision.url
      TWILIO_CONVERSATION_RELAY_URL        = "wss://${var.ws_domain_name}/twilio/conversation"
      TWILIO_VALIDATE_REQUESTS             = "true"
      TWILIO_VOICE_MODE                    = var.twilio_voice_mode
      UPLOAD_ALLOWED_CONTENT_TYPES         = "image/jpeg,image/png,image/webp"
      UPLOAD_LINK_BASE_URL                 = "https://${var.frontend_domain_name}/uploads"
      UPLOAD_MAX_BYTES                     = tostring(var.upload_max_bytes)
      UPLOAD_TOKEN_TTL_MINUTES             = tostring(var.upload_token_ttl_minutes)
      VISION_PRESIGNED_GET_EXPIRES_SECONDS = "600"
      } : {
      name  = name
      value = value
    }
  ]

  application_secrets = [
    {
      name      = "DATABASE_PASSWORD"
      valueFrom = local.database_password_secret_value_from
    },
    {
      name      = "OPENAI_API_KEY"
      valueFrom = local.openai_api_key_secret_arn
    },
    {
      name      = "TWILIO_AUTH_TOKEN"
      valueFrom = local.twilio_auth_token_secret_arn
    }
  ]

  tags = merge(
    {
      Project     = "SearsHomeServicesAiAgent"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Stack       = "backend"
    },
    var.tags,
  )
}
