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

variable "ci_cd_mode" {
  description = "When true, assume the GitHub Actions deployment role instead of using an SSO profile."
  type        = bool
  default     = false
}

variable "workload_sso_profile" {
  description = "Optional local AWS SSO profile for the Sears workload account."
  type        = string
  default     = ""
}

variable "vpc_cidr" {
  description = "CIDR block for the application VPC."
  type        = string
  default     = "10.42.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones to use. Keep explicit so validation does not require AWS data sources."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]

  validation {
    condition     = length(var.availability_zones) >= 2
    error_message = "At least two availability zones are required."
  }
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets."
  type        = list(string)
  default     = ["10.42.0.0/24", "10.42.1.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets."
  type        = list(string)
  default     = ["10.42.10.0/24", "10.42.11.0/24"]
}

variable "enable_nat_gateway" {
  description = "Create one NAT gateway for private subnet egress. Required for OpenAI and public API calls from private Fargate tasks."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Additional tags applied to shared resources."
  type        = map(string)
  default     = {}
}
