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
  description = "AWS region for workload resources. Keep us-east-1 for CloudFront ACM certificates."
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

variable "frontend_domain_name" {
  description = "Frontend hostname."
  type        = string
  default     = "shs.buildrlab.com"
}

variable "frontend_bucket_name" {
  description = "Optional exact S3 bucket name for static frontend assets."
  type        = string
  default     = null
}

variable "cloudfront_price_class" {
  description = "CloudFront price class."
  type        = string
  default     = "PriceClass_100"

  validation {
    condition = contains([
      "PriceClass_100",
      "PriceClass_200",
      "PriceClass_All",
    ], var.cloudfront_price_class)
    error_message = "CloudFront price class must be PriceClass_100, PriceClass_200, or PriceClass_All."
  }
}

variable "tags" {
  description = "Additional tags applied to frontend resources."
  type        = map(string)
  default     = {}
}
