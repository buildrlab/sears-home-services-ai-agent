provider "aws" {
  region  = var.aws_region
  profile = var.aws_sso_profile != "" ? var.aws_sso_profile : null

  default_tags {
    tags = local.tags
  }
}
