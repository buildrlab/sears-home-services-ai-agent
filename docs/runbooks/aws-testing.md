# AWS Testing Runbook

All AWS infrastructure is deployed through Terraform and GitHub Actions. Do not create durable infrastructure manually in the AWS console.

## Prerequisites

- AWS region: `us-east-1`.
- Sears workload account: `710045722740`.
- Terraform state bootstrapped in S3.
- GitHub OIDC configured for deployments.
- GitHub environments configured with required secrets.
- BuildrLab core DNS access configured:
  - DNS account: `buildrlab-core`
  - DNS account ID: `202612164956`
  - Parent hosted zone: `buildrlab.com`
  - Cross-account DNS provider/role configured the same way as `website` and `buildr-hq`
- Route 53 records configured directly in the parent `buildrlab.com` hosted zone for:
  - `shs.buildrlab.com`
  - `api.shs.buildrlab.com`
  - `ws.shs.buildrlab.com`
- No child hosted zone exists for `shs.buildrlab.com` unless a later ADR changes the DNS model.
- Twilio phone number configured for the deployed voice webhook.
- Twilio ConversationRelay enabled, or Gather fallback explicitly selected.
- SES sender identity verified.
- OpenAI API key stored in AWS Secrets Manager or GitHub Actions secrets.

## GitHub Deployment Configuration

Create a GitHub environment named `prod` for deployment approvals and secrets.

Required secret:

- `AWS_DEVOPS_ROLE_ARN`: IAM role in the BuildrLab devops/control account that
  GitHub OIDC can assume.

Runtime secret values:

- `OPENAI_API_KEY`: used to populate the backend Secrets Manager secret on deploy.
- `TWILIO_AUTH_TOKEN`: used to populate the backend Secrets Manager secret on deploy.

If the AWS Secrets Manager values already exist with an `AWSCURRENT` version,
the deploy workflow can proceed without the corresponding GitHub secret. First
live deploys should set both GitHub secrets so ECS secret injection cannot start
with empty Secrets Manager metadata.

Required variables:

- `AWS_DEVOPS_ACCOUNT_ID`: account that owns the GitHub OIDC devops role.
- `SHS_WORKLOAD_ACCOUNT_ID`: `710045722740`.
- `SHS_DNS_ACCOUNT_ID`: `202612164956`.
- `SHS_HOSTED_ZONE_ID`: `Z05781442GINHB3A5IJXK`.
- `TF_STATE_BUCKET`: `buildrlab-terraform-state`.

Check deployment readiness from the repo root:

```bash
python3.14 scripts/aws/deploy_preflight.py
```

This command is read-only. It reports missing GitHub environment-scoped secrets
and variables, deployment environment configuration, `dev` branch protection,
local GitHub CLI auth, and AWS CLI credentials before anyone triggers the deploy
workflow.

To configure the GitHub deployment environment after `gh auth login` succeeds:

```bash
python3.14 scripts/github/configure_deploy.py \
  --aws-devops-account-id "<devops-account-id>" \
  --apply
```

To also set environment-scoped secrets from local environment variables, add
`--include-secrets`. See `scripts/github/README.md`.

To configure the conservative `dev` branch protection policy after `gh auth
login` succeeds:

```bash
python3.14 scripts/github/configure_branch_protection.py --apply
```

Terraform assumes these target roles from the devops role:

- Workload account: `prod-sears-home-services-ai-agent-deploy`.
- DNS account: `sears-home-services-ai-agent-prod-route53-delegation`.

## State Bootstrap

The normal app deploy workflow assumes the S3 Terraform state bucket already
exists. If it does not, apply `infra/bootstrap` once from an approved admin
context before running `.github/workflows/aws-deploy.yml`:

```bash
cd infra/bootstrap
terraform init
terraform apply \
  -var 'state_bucket_name=buildrlab-terraform-state' \
  -var 'environment=prod'
```

After bootstrap, the app stacks use S3 remote state with native S3 lockfiles.

## Deployment Path

1. Open a pull request into `dev`.
2. Confirm backend, frontend, Terraform, and security checks pass.
3. Review the Terraform plan in GitHub Actions.
4. Confirm the DNS plan uses the cross-account `aws.dns` provider against the parent `buildrlab.com` hosted zone.
5. Confirm the DNS plan does not create a Sears-owned `shs.buildrlab.com` hosted zone.
6. Confirm the backend plan deploys ECS/Fargate services/tasks, not a Lambda API runtime.
7. Merge only after checks and plan are understood.
8. Deploy through `.github/workflows/aws-deploy.yml`.

See [GitHub Branch Protection Runbook](github-branch-protection.md) for the
recommended `dev` and `main` merge gates.

Stack order:

1. `infra/bootstrap`
2. `infra/shared`
3. `backend/infra`
4. `frontend/infra`

Local validation without deploying:

```bash
scripts/terraform/validate.sh
```

First backend deployment through GitHub Actions:

1. Open **Actions -> AWS Deploy**.
2. Select environment `prod`.
3. Select mode `apply`.
4. Set `bootstrap_backend=true`.
5. Keep `api_desired_count=1` and `worker_desired_count=1` unless deliberately
   doing a zero-task infrastructure-only apply.
6. Confirm the workflow creates shared infrastructure, creates backend resources
   with zero running tasks, pushes the backend image, verifies secret values,
   applies ECS services, runs the Alembic Fargate migration task, deploys the
   frontend, and runs remote smoke checks.

Subsequent deployments:

1. Run the workflow in `plan` mode after shared state exists.
2. Review the Terraform plan output.
3. Rerun in `apply` mode with `bootstrap_backend=false`.

## AWS Teardown

When the project is over, use **Actions -> AWS Destroy**. Do not delete
resources manually in the AWS console.

Recommended sequence:

1. Run `.github/workflows/aws-destroy.yml` with `mode=plan`.
2. Review the destroy plans for `frontend/infra`, `backend/infra`, and, if
   selected, `infra/shared`.
3. Rerun with `mode=destroy`.
4. Set `delete_data=true`.
5. Keep `skip_final_snapshot=false` unless the database is already backed up or
   disposable.
6. Enter confirmation text exactly:

```text
destroy sears-home-services-ai-agent prod
```

Use `scope=app-only` to remove CloudFront/S3, API, ECS/Fargate, Aurora, SQS,
SES, Secrets Manager, ALB, and app DNS records while keeping the shared VPC,
ECS cluster, and deployment IAM. Use `scope=all-including-shared` only for final
project teardown.

The destroy workflow intentionally does not destroy `infra/bootstrap` or the
shared Terraform state bucket. It disables backend deletion protections, scales
Fargate services to zero, and enables force deletion for managed S3 buckets and
ECR only after `delete_data=true`.

## Database Migrations

Production Alembic migrations must run outside the normal API runtime. Do not
run `alembic upgrade head` during container startup, FastAPI startup, Lambda
import, or request handling.

The deployment path includes an explicit migration step. The runner is a one-off
ECS/Fargate task in the application VPC, using the same backend image as the API
service and a least-privilege migration role:

```bash
aws ecs run-task \
  --cluster "<ecs_cluster_name>" \
  --task-definition "<migration_task_definition_arn>" \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-private-a,subnet-private-b],securityGroups=[sg-backend-tasks],assignPublicIp=DISABLED}"
```

The task command is `alembic upgrade head && python -m app.seed`. It reads the
generated Aurora password from the RDS-managed Secrets Manager secret. Run only
one migration task at a time. Alembic migrations and seed updates must remain
backward compatible with the previous API image because ECS rolling deployments
can briefly run old and new tasks during a service deployment.

Useful outputs:

```bash
terraform -chdir=infra/shared output -raw ecs_cluster_name
terraform -chdir=infra/shared output -json private_subnet_ids
terraform -chdir=backend/infra output -raw migration_task_definition_arn
terraform -chdir=backend/infra output -raw ecs_tasks_security_group_id
```

## DNS Verification

Before API and frontend smoke tests:

```bash
dig +short shs.buildrlab.com
dig +short api.shs.buildrlab.com
dig +short ws.shs.buildrlab.com
```

See [DNS Delegation Runbook](dns-delegation.md).

## Remote Smoke Tests

After deployment, verify:

```bash
curl -f https://api.shs.buildrlab.com/healthz
```

Then run the project smoke suite:

```bash
python3.14 scripts/aws/remote_smoke.py \
  --api-base-url https://api.shs.buildrlab.com \
  --frontend-base-url https://shs.buildrlab.com
```

## Remote Frontend Tests

Run Playwright against the deployed frontend:

```bash
cd frontend
PLAYWRIGHT_BASE_URL=https://shs.buildrlab.com pnpm test:e2e
```

The run must pass without unexpected browser console errors.
Confirm the deployed frontend was built with
`VITE_API_BASE_URL=https://api.shs.buildrlab.com`.

## Twilio Verification

Call the configured Twilio number and verify:

- The call reaches `https://api.shs.buildrlab.com/twilio/voice/incoming`.
- ConversationRelay connects to `wss://ws.shs.buildrlab.com/twilio/conversation`, or Gather fallback works if ConversationRelay is unavailable.
- Twilio signatures are validated.
- A call session is persisted.
- Appliance and symptom collection works.
- Scheduling can book an appointment.

The final automated deployed check validates the signed webhook path without
disabling production signature validation:

```bash
AWS_PROFILE=sears python3.14 scripts/aws/final_live_smoke.py \
  --api-base-url https://api.shs.buildrlab.com \
  --email-to no-reply@shs.buildrlab.com
```

This posts production-valid Twilio signatures to the deployed incoming, Gather,
and status callback routes, then verifies voice appointment proposal and booking
confirmation. It complements, but does not replace, a manual carrier call when a
reviewer wants to hear the phone flow.

## Tier 3 Verification

During or after a call:

- Capture caller email.
- Send upload link through SES.
- Confirm the upload link points to `https://shs.buildrlab.com/uploads/<token>`.
- Confirm the email is received.
- Upload a valid appliance image.
- Confirm invalid file types and oversized files are rejected.
- Confirm image metadata is stored.
- Confirm OpenAI vision analysis runs.
- Confirm the diagnostic session shows the visual analysis result.

SES send is implemented and verified. The AWS account is currently in sandbox
mode with a 200 emails/day quota, and production access has been requested.

## AWS Log Review

After every remote test run, review:

- ALB target errors.
- ECS task crashes, deployment failures, and container health check failures.
- Aurora connection issues.
- SQS dead-letter queue messages.
- SES send failures.
- S3 access denied events.
- CloudWatch alarms.

Fix any observed runtime errors and rerun the relevant tests.

## Security Review

Before submission:

- Confirm no secrets are committed.
- Confirm Terraform uses least-privilege IAM.
- Confirm S3 buckets block public access unless explicitly justified.
- Confirm upload URLs are short-lived.
- Confirm CORS allows only expected origins.
- Confirm dependency and security scans pass.
- Confirm deployed resources are cost-conscious and unnecessary resources are removed.
