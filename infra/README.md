# Infrastructure

Terraform manages all AWS infrastructure.

## State

Terraform state must be stored in S3. Bootstrap resources live under `infra/bootstrap` and are applied deliberately before environment infrastructure.

## Layout

- `infra/bootstrap`: S3 state bucket and related bootstrap resources.
- `infra/shared`: shared AWS resources such as DNS, GitHub OIDC, VPC, and IAM.
- `backend/infra`: backend resources such as API Gateway, Lambda, Aurora, RDS Proxy, S3, SQS, SES, Secrets Manager, and CloudWatch.
- `frontend/infra`: frontend S3/CloudFront resources.

