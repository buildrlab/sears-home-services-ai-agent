# Infrastructure

Terraform manages all AWS infrastructure.

## State

Terraform state must be stored in S3. Bootstrap resources live under `infra/bootstrap` and are applied deliberately before environment infrastructure.

## DNS Boundary

Use the established BuildrLab cross-account DNS pattern from the `website` and `buildr-hq` projects.

- `buildrlab-core` account `202612164956` owns the existing `buildrlab.com` Route 53 hosted zone.
- Sears Terraform uses a DNS provider alias to assume a Route 53 delegation role in `buildrlab-core`.
- Sears DNS records are created directly in the parent `buildrlab.com` hosted zone.
- Do not create a separate `shs.buildrlab.com` hosted zone in the Sears workload account.

## Layout

- `infra/bootstrap`: S3 state bucket and related bootstrap resources.
- `infra/shared`: shared AWS resources such as DNS, GitHub OIDC, VPC, and IAM.
- `backend/infra`: backend resources such as API Gateway, Lambda, Aurora, RDS Proxy, S3, SQS, SES, Secrets Manager, and CloudWatch.
- `frontend/infra`: frontend S3/CloudFront resources.
