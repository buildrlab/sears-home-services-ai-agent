# Backend Terraform

This directory manages backend AWS resources:

- ECR repository for the Python/FastAPI image.
- Public ALB with HTTPS and HTTP redirect.
- ECS/Fargate API service.
- ECS/Fargate SQS vision worker service.
- One-off ECS/Fargate Alembic migration and technician seed task definition.
- Aurora Serverless v2 PostgreSQL-compatible cluster.
- KMS keys for Aurora and appliance image uploads.
- S3 bucket for appliance image uploads with SSE-KMS, public access block, and lifecycle cleanup.
- SQS vision queue and dead-letter queue.
- SES domain identity and DNS validation records.
- Secrets Manager metadata for OpenAI and Twilio secrets.
- CloudWatch log groups.
- Route 53 records for `api.shs.buildrlab.com` and `ws.shs.buildrlab.com`
  through the BuildrLab core DNS provider alias.

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
# Fill vpc_id, subnet IDs, and ECS cluster outputs from infra/shared.
terraform init -backend-config=backend.hcl
terraform plan -var-file=prod.tfvars
```

## Required Secret Values

Terraform creates secret metadata when `openai_api_key_secret_arn` or
`twilio_auth_token_secret_arn` is null. Set values before starting ECS tasks:

```bash
aws secretsmanager put-secret-value \
  --secret-id /sears-home-services-ai-agent-prod/openai-api-key \
  --secret-string "$OPENAI_API_KEY"

aws secretsmanager put-secret-value \
  --secret-id /sears-home-services-ai-agent-prod/twilio-auth-token \
  --secret-string "$TWILIO_AUTH_TOKEN"
```

Aurora uses `manage_master_user_password = true`; ECS injects the generated RDS
password directly from the RDS-managed Secrets Manager secret as
`DATABASE_PASSWORD`. Terraform does not require a database password variable.

## Alembic Migration Task

Do not run migrations during FastAPI startup or container startup. After the new
image is pushed and the migration task definition is registered, run:

```bash
aws ecs run-task \
  --cluster "<ecs_cluster_name>" \
  --task-definition "<migration_task_definition_arn>" \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-private-a,subnet-private-b],securityGroups=[sg-backend-tasks],assignPublicIp=DISABLED}"
```

Use `terraform -chdir=infra/shared output -raw ecs_cluster_name`,
`terraform -chdir=infra/shared output -json private_subnet_ids`,
`terraform -chdir=backend/infra output -raw migration_task_definition_arn`, and
`terraform -chdir=backend/infra output -raw ecs_tasks_security_group_id` to fill
the placeholders. The task command is:

```bash
alembic upgrade head && python -m app.seed
```

Every deployment applies migrations and verifies the representative technician
data required by the take-home. Only after the task exits successfully should
the API service be updated and remote smoke tests run.
