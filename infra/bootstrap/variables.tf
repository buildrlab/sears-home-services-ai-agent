variable "project_name" {
  description = "Project slug used for tagging bootstrap resources."
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
  description = "AWS region for the Terraform state bucket."
  type        = string
  default     = "us-east-1"
}

variable "aws_sso_profile" {
  description = "Optional local AWS SSO profile for bootstrapping state."
  type        = string
  default     = ""
}

variable "state_bucket_name" {
  description = "S3 bucket name for Terraform remote state."
  type        = string
  default     = "buildrlab-terraform-state"
}

variable "force_destroy_state_bucket" {
  description = "Allow Terraform to destroy a non-empty state bucket. Keep false outside disposable sandboxes."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Additional tags applied to bootstrap resources."
  type        = map(string)
  default     = {}
}
