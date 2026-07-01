# Frontend Terraform

This directory manages frontend AWS resources:

- Private SSE-KMS S3 bucket for Vite build output.
- CloudFront distribution with origin access control.
- AWS WAF managed common rules for the CloudFront distribution.
- ACM certificate for `shs.buildrlab.com`.
- Route 53 `A` and `AAAA` alias records through the BuildrLab core DNS provider alias.
- SPA fallback for `/uploads/<token>` and dashboard routes.

All state is remote S3 state after bootstrap.

## Local Validation

```bash
terraform init -backend=false
terraform validate
```

Or from the repo root:

```bash
scripts/terraform/validate.sh
```

## Local Plan

```bash
cp backend.hcl.example backend.hcl
cp prod.tfvars.example prod.tfvars
terraform init -backend-config=backend.hcl
terraform plan -var-file=prod.tfvars
```

## Asset Deployment

Build the frontend with the deployed API URL:

```bash
VITE_API_BASE_URL=https://api.shs.buildrlab.com pnpm build
```

Upload assets after Terraform has created the bucket:

```bash
aws s3 sync dist/ "s3://$(terraform output -raw frontend_bucket_name)/" --delete
aws cloudfront create-invalidation \
  --distribution-id "$(terraform output -raw cloudfront_distribution_id)" \
  --paths "/*"
```
