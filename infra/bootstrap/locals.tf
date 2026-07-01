locals {
  tags = merge(
    {
      Project     = "SearsHomeServicesAiAgent"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Stack       = "bootstrap"
    },
    var.tags,
  )
}
