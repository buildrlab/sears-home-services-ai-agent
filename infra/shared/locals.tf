locals {
  name_prefix = "${var.project_name}-${var.environment}"
  subnet_indexes = {
    for index, zone in var.availability_zones : zone => index
  }
  tags = merge(
    {
      Project     = "SearsHomeServicesAiAgent"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Stack       = "shared"
    },
    var.tags,
  )
}
