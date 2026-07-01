# Infrastructure

Terraform manages all AWS infrastructure.

## State

Terraform state must be stored in S3. Bootstrap resources live under `infra/bootstrap` and are applied deliberately before environment infrastructure.

Remote backend examples use the shared `buildrlab-terraform-state` bucket and
Terraform's native S3 `use_lockfile = true` setting. This avoids a DynamoDB lock
table while still preventing concurrent state writes.

## DNS Boundary

Use the established BuildrLab cross-account DNS pattern from the `website` and `buildr-hq` projects.

- `buildrlab-core` account `202612164956` owns the existing `buildrlab.com` Route 53 hosted zone.
- Sears Terraform uses a DNS provider alias to assume a Route 53 delegation role in `buildrlab-core`.
- Sears DNS records are created directly in the parent `buildrlab.com` hosted zone.
- Do not create a separate `shs.buildrlab.com` hosted zone in the Sears workload account.

## Layout

- `infra/bootstrap`: S3 state bucket and related bootstrap resources.
- `infra/shared`: shared AWS resources such as DNS, GitHub OIDC, VPC, and IAM.
- `backend/infra`: backend resources such as ALB, ECS/Fargate, ECR, Aurora, S3, SQS, SES, Secrets Manager, and CloudWatch.
- `frontend/infra`: frontend S3/CloudFront resources.

## Local Validation

```bash
scripts/terraform/validate.sh
```

The validation script runs `terraform fmt -check`, `terraform init
-backend=false`, and `terraform validate` for all Terraform stacks. It does not
create AWS resources.

## Deployment Order

1. `infra/bootstrap`
2. `infra/shared`
3. `backend/infra`
4. `frontend/infra`

Pass `infra/shared` outputs into `backend/infra` through environment-specific
tfvars or GitHub Actions outputs. Do not use manual console-created application
resources.

## Teardown

Use `.github/workflows/aws-destroy.yml` when the project is over. It is
manual-only, defaults to non-mutating `plan` mode, and requires the exact
confirmation text `destroy sears-home-services-ai-agent prod` before deleting
resources.

The workflow destroys stacks in reverse order:

1. `frontend/infra`
2. `backend/infra`
3. `infra/shared` only when `scope=all-including-shared`

It intentionally does not destroy `infra/bootstrap` or the shared Terraform
state bucket. The backend destroy path disables ALB and Aurora deletion
protection, scales Fargate services to zero, and enables Terraform's explicit
ECR/S3 force-delete flags only when `delete_data=true`.
