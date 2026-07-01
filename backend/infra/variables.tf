variable "project_name" {
  description = "Project slug used in resource names."
  type        = string
  default     = "sears-home-services-ai-agent"

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "Project name must contain only lowercase letters, numbers, and hyphens."
  }
}

variable "environment" {
  description = "Environment name."
  type        = string
  default     = "prod"

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be dev or prod."
  }
}

variable "aws_region" {
  description = "AWS region for workload resources."
  type        = string
  default     = "us-east-1"
}

variable "workload_account_id" {
  description = "Sears workload AWS account ID."
  type        = string
}

variable "dns_account_id" {
  description = "BuildrLab core DNS account ID."
  type        = string
  default     = "202612164956"
}

variable "hosted_zone_id" {
  description = "Route 53 hosted zone ID for buildrlab.com in the DNS account."
  type        = string
}

variable "ci_cd_mode" {
  description = "When true, assume deployment roles instead of using local SSO profiles."
  type        = bool
  default     = false
}

variable "workload_sso_profile" {
  description = "Optional local AWS SSO profile for the Sears workload account."
  type        = string
  default     = ""
}

variable "dns_sso_profile" {
  description = "Optional local AWS SSO profile for the BuildrLab core DNS account."
  type        = string
  default     = "buildrlab-core"
}

variable "vpc_id" {
  description = "Shared VPC ID from infra/shared."
  type        = string
}

variable "public_subnet_ids" {
  description = "Public subnet IDs for the internet-facing ALB."
  type        = list(string)
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for Fargate tasks and Aurora."
  type        = list(string)
}

variable "ecs_cluster_arn" {
  description = "Shared ECS cluster ARN from infra/shared."
  type        = string
}

variable "ecs_cluster_name" {
  description = "Shared ECS cluster name from infra/shared."
  type        = string
}

variable "api_domain_name" {
  description = "Public API hostname."
  type        = string
  default     = "api.shs.buildrlab.com"
}

variable "ws_domain_name" {
  description = "Public Twilio ConversationRelay WebSocket hostname."
  type        = string
  default     = "ws.shs.buildrlab.com"
}

variable "frontend_domain_name" {
  description = "Frontend hostname used for CORS and upload links."
  type        = string
  default     = "shs.buildrlab.com"
}

variable "backend_image_tag" {
  description = "Backend container image tag to deploy. CI should pass the Git SHA."
  type        = string
  default     = "bootstrap"
}

variable "api_desired_count" {
  description = "Desired API task count."
  type        = number
  default     = 1
}

variable "worker_desired_count" {
  description = "Desired SQS vision worker task count."
  type        = number
  default     = 1
}

variable "task_cpu" {
  description = "Fargate task CPU units."
  type        = number
  default     = 512
}

variable "task_memory" {
  description = "Fargate task memory in MiB."
  type        = number
  default     = 1024
}

variable "cpu_architecture" {
  description = "Fargate CPU architecture."
  type        = string
  default     = "X86_64"

  validation {
    condition     = contains(["X86_64", "ARM64"], var.cpu_architecture)
    error_message = "CPU architecture must be X86_64 or ARM64."
  }
}

variable "database_name" {
  description = "Application database name."
  type        = string
  default     = "shs_ai_agent"
}

variable "database_master_username" {
  description = "Aurora master username."
  type        = string
  default     = "shs_admin"
}

variable "aurora_postgresql_engine_version" {
  description = "Optional Aurora PostgreSQL engine version. Leave null to let AWS select the current default supported version in the region."
  type        = string
  default     = null
}

variable "aurora_min_capacity" {
  description = "Aurora Serverless v2 minimum ACUs."
  type        = number
  default     = 0.5
}

variable "aurora_max_capacity" {
  description = "Aurora Serverless v2 maximum ACUs."
  type        = number
  default     = 2
}

variable "enable_alb_deletion_protection" {
  description = "Enable ALB deletion protection. Null keeps the production-safe default."
  type        = bool
  default     = null
}

variable "database_deletion_protection" {
  description = "Enable Aurora deletion protection."
  type        = bool
  default     = true
}

variable "database_skip_final_snapshot" {
  description = "Skip final snapshot on database deletion. Keep false for production unless deliberately tearing down."
  type        = bool
  default     = false
}

variable "upload_bucket_name" {
  description = "Optional exact S3 bucket name for uploaded appliance images."
  type        = string
  default     = null
}

variable "upload_bucket_force_destroy" {
  description = "Allow Terraform to delete non-empty upload buckets during deliberate project teardown."
  type        = bool
  default     = false
}

variable "ecr_force_delete" {
  description = "Allow Terraform to delete the backend ECR repository even when images remain during deliberate project teardown."
  type        = bool
  default     = false
}

variable "upload_token_ttl_minutes" {
  description = "Secure upload link TTL."
  type        = number
  default     = 60
}

variable "upload_max_bytes" {
  description = "Maximum image upload size in bytes."
  type        = number
  default     = 10485760
}

variable "allowed_cors_origins" {
  description = "Allowed backend CORS origins."
  type        = list(string)
  default     = ["https://shs.buildrlab.com"]
}

variable "twilio_voice_mode" {
  description = "Twilio voice mode."
  type        = string
  default     = "gather"

  validation {
    condition     = contains(["gather", "conversationrelay"], var.twilio_voice_mode)
    error_message = "Twilio voice mode must be gather or conversationrelay."
  }
}

variable "openai_model" {
  description = "OpenAI model for text diagnostics."
  type        = string
  default     = "gpt-5.5"
}

variable "openai_vision_model" {
  description = "OpenAI model for vision diagnostics."
  type        = string
  default     = "gpt-5.5"
}

variable "openai_api_key_secret_arn" {
  description = "Existing Secrets Manager ARN containing the OpenAI API key. If null, Terraform creates secret metadata and you must set the value before starting ECS tasks."
  type        = string
  default     = null
}

variable "twilio_auth_token_secret_arn" {
  description = "Existing Secrets Manager ARN containing the Twilio auth token. If null, Terraform creates secret metadata and you must set the value before starting ECS tasks."
  type        = string
  default     = null
}

variable "email_domain" {
  description = "SES domain identity for upload-link emails."
  type        = string
  default     = "shs.buildrlab.com"
}

variable "email_from_address" {
  description = "SES From address for upload-link emails."
  type        = string
  default     = "Sears Home Services <no-reply@shs.buildrlab.com>"
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days."
  type        = number
  default     = 30
}

variable "tags" {
  description = "Additional tags applied to backend resources."
  type        = map(string)
  default     = {}
}
