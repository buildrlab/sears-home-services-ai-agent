# Backend

Python backend for the Sears Home Services voice AI appliance diagnostic agent.

## Planned Stack

- Python
- FastAPI
- SQLAlchemy 2.0
- Alembic
- PostgreSQL
- Pytest
- Ruff
- Twilio SDK
- OpenAI SDK
- AWS SDK for Python

## Responsibilities

- Twilio inbound webhook.
- Twilio ConversationRelay WebSocket handler.
- Twilio Gather fallback flow.
- Diagnostic conversation orchestration.
- Technician scheduling.
- Image upload token creation.
- SES email sending.
- S3 upload coordination.
- SQS vision worker.

## Testing

Backend implementation must include:

- Unit tests.
- Functional API tests.
- Integration tests against local Postgres.
- Alembic migration tests.
- Twilio signature validation tests.
- Scheduling race-condition tests.

## Infrastructure

Backend AWS resources are managed from `backend/infra` using Terraform.

