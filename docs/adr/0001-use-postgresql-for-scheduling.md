# ADR 0001: Use PostgreSQL Instead of DynamoDB for Scheduling

## Status

Accepted

## Context

The system needs to match technicians by service area, appliance specialty, and available time slots. It must prevent double-booking, preserve appointment history, and support reviewer-friendly inspection of the scheduling model.

The core scheduling access patterns are:

- Find technicians who service a caller's ZIP code and appliance type.
- Find open slots for matched technicians in a caller's preferred time window.
- Hold or book exactly one slot for exactly one customer.
- Prevent concurrent callers from booking the same slot.
- Show appointment history for a call session, customer, or technician.
- Seed and inspect 5-10 sample technicians across ZIP codes and specialties.

The data has natural relationships:

- A technician covers many service areas.
- A technician has many appliance specialties.
- A technician has many availability slots.
- A customer can have many appointments.
- An appointment belongs to one customer, one technician, and one availability slot.

## Decision

Use PostgreSQL for scheduling data. Use local PostgreSQL in Docker Compose and Aurora Serverless v2 PostgreSQL in AWS.

Use SQLAlchemy 2.0 for application data access and Alembic for schema migrations.

## Consequences

- Relational constraints and transactions can enforce scheduling correctness.
- Alembic migrations provide a reviewable schema-change history.
- Lambda database connections require RDS Proxy and careful pooling.
- PostgreSQL is less serverless-native than DynamoDB, but it fits the scheduling domain better.
- The schema can encode important invariants with foreign keys, unique constraints, check constraints, and transactional updates.
- Query flexibility remains high while the scheduling workflow is still evolving during the take-home implementation.

## Why PostgreSQL Fits Better

PostgreSQL is the better primary store for this domain because scheduling correctness depends on relational integrity and transactional behavior.

Examples:

- `appointments.slot_id` can be unique so two appointments cannot book the same slot.
- `availability_slots.status` can be constrained to known states such as `open`, `held`, `booked`, and `expired`.
- Booking can run inside a transaction that checks slot availability, creates an appointment, and marks the slot as booked.
- Foreign keys keep appointments linked to real customers, technicians, and slots.
- Joins make reviewer-facing queries straightforward: "show all booked appointments with technician, ZIP, specialty, and call session context."

## Why Not DynamoDB as the Primary Scheduling Store

DynamoDB is operationally attractive for serverless systems, but it is not the best primary database for this scheduling model.

Reasons:

- DynamoDB requires access-pattern-first modeling, while this project benefits from visible relational modeling.
- Many-to-many relationships for technician service areas and specialties are simpler and clearer in SQL.
- Flexible reviewer/debug queries would require duplicated items, GSIs, or denormalized projections.
- Preventing double-booking would require careful conditional writes or transactions on slot items.
- Schema evolution and review are less explicit than SQL migrations with Alembic.

DynamoDB would be a reasonable choice for high-scale, fixed-access-pattern call/session state, but the take-home's scheduling requirement is consistency-heavy and relational. Keeping PostgreSQL as the single primary data store also reduces implementation complexity.

## Alternatives Considered

- DynamoDB: operationally simple and serverless, but requires access-pattern-first modeling, denormalization, GSIs, and conditional writes for scheduling correctness.
- SQLite: simple locally, but not representative of the deployed scheduling system and weaker for concurrent booking validation.

## Revisit Criteria

Reconsider DynamoDB only if:

- The scheduling access patterns become fixed and extremely high-volume.
- Aurora cost or VPC/Lambda connection overhead becomes a measured issue.
- The system needs globally distributed low-latency reads/writes beyond the take-home scope.
- Scheduling is split from call/session state and only ephemeral session data needs a NoSQL store.
