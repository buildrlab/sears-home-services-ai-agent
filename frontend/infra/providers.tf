provider "aws" {
  region  = var.aws_region
  profile = var.workload_sso_profile != "" ? var.workload_sso_profile : null

  dynamic "assume_role" {
    for_each = var.ci_cd_mode ? [1] : []
    content {
      role_arn     = "arn:aws:iam::${var.workload_account_id}:role/${var.environment}-${var.project_name}-deploy"
      session_name = "terraform-shs-frontend"
    }
  }

  default_tags {
    tags = local.tags
  }
}

provider "aws" {
  alias   = "dns"
  region  = var.aws_region
  profile = var.dns_sso_profile != "" ? var.dns_sso_profile : null

  dynamic "assume_role" {
    for_each = var.ci_cd_mode ? [1] : []
    content {
      role_arn     = "arn:aws:iam::${var.dns_account_id}:role/${var.project_name}-${var.environment}-route53-delegation"
      session_name = "terraform-shs-frontend-dns"
    }
  }
}
