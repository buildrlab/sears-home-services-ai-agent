provider "aws" {
  region  = var.aws_region
  profile = var.workload_sso_profile != "" ? var.workload_sso_profile : null

  dynamic "assume_role" {
    for_each = var.ci_cd_mode ? [1] : []
    content {
      role_arn     = "arn:aws:iam::${var.workload_account_id}:role/${var.environment}-${var.project_name}-deploy"
      session_name = "terraform-shs-shared"
    }
  }

  default_tags {
    tags = local.tags
  }
}
