locals {
  name_prefix          = "${var.project_name}-${var.environment}"
  frontend_bucket_name = coalesce(var.frontend_bucket_name, "${local.name_prefix}-frontend-${var.workload_account_id}")
  s3_origin_id         = "${local.name_prefix}-frontend-s3"

  tags = merge(
    {
      Project     = "SearsHomeServicesAiAgent"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Stack       = "frontend"
    },
    var.tags,
  )
}
