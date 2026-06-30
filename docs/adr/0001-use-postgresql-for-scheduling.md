# ADR 0001: Use PostgreSQL for Scheduling

## Status

Accepted

## Context

The system needs to match technicians by service area, appliance specialty, and available time slots. It must prevent double-booking and preserve appointment history.

## Decision

Use PostgreSQL for scheduling data. Use local PostgreSQL in Docker Compose and Aurora Serverless v2 PostgreSQL in AWS.

## Consequences

- Relational constraints and transactions can enforce scheduling correctness.
- Alembic migrations provide a reviewable schema-change history.
- Lambda database connections require RDS Proxy and careful pooling.
- PostgreSQL is less serverless-native than DynamoDB, but it fits the scheduling domain better.

## Alternatives Considered

- DynamoDB: operationally simple and serverless, but requires access-pattern-first modeling and conditional writes for scheduling correctness.
- SQLite: simple locally, but not representative of the deployed scheduling system.

