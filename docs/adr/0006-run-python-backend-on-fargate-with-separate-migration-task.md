# ADR 0006: Run Python Backend on Fargate With Separate Migration Task

## Status

Accepted

## Context

The backend uses PostgreSQL and Alembic for schema migrations. The earlier
serverless plan favored AWS Lambda for the Python API where possible, with
Alembic as a separate deployment step. The user asked whether Lambda cold starts
and Alembic execution risk make Fargate a better fit for the Python layer.

The application also has Twilio voice and ConversationRelay requirements, which
are easier to reason about with a long-running ASGI container than with API
Gateway/Lambda WebSocket handlers. Fargate remains serverless compute in the AWS
sense: the project runs containers without managing EC2 hosts, while accepting a
small always-on service cost for simpler operations and lower integration risk.

Migrations still need stronger deployment ordering and broader database
permissions than the request-time API should hold. They should not run during
container startup or request handling.

## Decision

Run the Python backend on Amazon ECS with AWS Fargate.

The primary Python runtime will be a FastAPI container service behind an
Application Load Balancer:

- one ECS/Fargate service for the API, Twilio webhooks, and ConversationRelay
  WebSocket endpoint,
- one ECS/Fargate one-off migration task that runs the same backend image with
  `alembic upgrade head`,
- one ECS/Fargate worker service or scheduled task for Python async processing
  if SQS vision processing needs a long-running worker. If Phase 5 shows that
  Lambda is materially simpler for the worker, record that as a narrow exception
  in a later ADR.

Alembic migrations must run as a separate deployment step before traffic is
shifted to the new backend service revision. The migration runner must use
least-privilege IAM, read the database secret from AWS Secrets Manager, and run
with deployment-level concurrency controls so two migrations cannot run at the
same time.

The API service must assume the schema is already current. It may run lightweight
health checks, but it must not mutate schema on import, startup, or request.

## Consequences

- The Python runtime has one container packaging and deployment path instead of
  Lambda plus separate migration compute.
- Twilio WebSocket behavior can run in the same ASGI app as the rest of the API.
- The API task role can have narrower database privileges than the migration
  role.
- GitHub Actions deployment must include an explicit migration step between
  Terraform/app packaging and ECS service rollout.
- Local development continues to run `alembic upgrade head` directly.
- AWS deployment runbooks must document migration execution and rollback
  expectations.
- Fargate plus ALB has higher idle cost than Lambda/API Gateway for very low
  traffic, but it reduces architecture risk for the take-home.

## Alternatives Considered

### Run Alembic Inside Lambda Startup

Rejected. This increases cold-start latency, can fail during user traffic,
requires broader Lambda database privileges, and creates concurrency risk when
multiple Lambda environments initialize around the same deployment.

### Lambda API With Separate Fargate Migration Task

Considered. This is cost-efficient for low request volume and keeps API Gateway
plus Lambda serverless scaling. If chosen, the Python layer would likely be one
FastAPI Lambda for request/response API routes, one SQS worker Lambda for image
analysis, and separate WebSocket handlers if using API Gateway WebSocket APIs.
Alembic would still run as a separate ECS/Fargate or VPC-enabled CodeBuild task.

Rejected for this project because Fargate gives a simpler and more coherent
reviewer-ready architecture for FastAPI, Twilio webhooks, ConversationRelay, and
migrations.

### GitHub-Hosted Runner Runs Alembic Directly

Rejected as the default because the production database should live in private
subnets. A GitHub-hosted runner usually should not have direct network access to
private Aurora. Self-hosted runners remain possible, but they add operational
overhead for this take-home.

## Review Date

Review during Phase 7 infrastructure implementation after the final API, worker,
and WebSocket paths are known.
