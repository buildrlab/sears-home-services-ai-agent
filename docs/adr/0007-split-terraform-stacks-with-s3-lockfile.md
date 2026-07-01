# ADR 0007: Split Terraform Stacks With S3 State Lockfiles

## Status

Accepted.

## Context

The project has separate frontend, backend, and shared AWS ownership boundaries.
The user requires Terraform-managed AWS infrastructure, S3 remote state, GitHub
Actions deployments, and local validation without requiring live AWS credentials.

The existing BuildrLab projects use an S3 state bucket and cross-account DNS
provider pattern. Terraform 1.10 and newer support native S3 state lockfiles,
which avoids adding DynamoDB solely for state locking.

## Decision

Use four Terraform stacks:

- `infra/bootstrap`: remote state bucket bootstrap.
- `infra/shared`: VPC, subnets, NAT egress, and ECS cluster.
- `backend/infra`: ECR, ALB, ECS/Fargate API and worker services, one-off
  Alembic migration task definition, Aurora Serverless v2, S3 uploads, SQS,
  SES, Secrets Manager metadata, CloudWatch, ACM, and backend DNS records.
- `frontend/infra`: S3 static asset bucket, CloudFront, ACM, and frontend DNS.

Each remote backend uses the shared `buildrlab-terraform-state` S3 bucket with
`use_lockfile = true`. Stack inputs are passed explicitly through tfvars or CI
outputs rather than hidden remote-state reads so `terraform validate` can run
locally with `-backend=false`.

## Consequences

- The stack split matches ownership boundaries and keeps plans reviewable.
- Terraform validation works without AWS credentials after provider
  initialization.
- S3 lockfiles avoid a DynamoDB table and reduce cost/operational surface.
- Deployment ordering is explicit: bootstrap, shared, backend, frontend.
- CI must pass shared stack outputs into backend and frontend deploy jobs.

## Alternatives Considered

### Single Terraform Root

Rejected because a single plan would be larger, harder to review, and more
likely to couple frontend deploys to backend database changes.

### Remote State Data Sources Between Stacks

Rejected for this take-home because it makes local validation require backend
configuration and AWS state access. Explicit inputs are easier to review.

### DynamoDB State Lock Table

Rejected because native S3 lockfiles satisfy the locking requirement with fewer
AWS resources and lower cost.
