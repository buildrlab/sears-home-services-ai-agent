output "frontend_url" {
  description = "Public frontend URL."
  value       = "https://${var.frontend_domain_name}"
}

output "frontend_bucket_name" {
  description = "S3 bucket for built frontend assets."
  value       = aws_s3_bucket.frontend.bucket
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID."
  value       = aws_cloudfront_distribution.frontend.id
}

output "cloudfront_domain_name" {
  description = "CloudFront distribution domain name."
  value       = aws_cloudfront_distribution.frontend.domain_name
}
