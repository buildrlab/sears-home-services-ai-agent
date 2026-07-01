"""Create diagnostic session schema.

Revision ID: 0003_diagnostic_schema
Revises: 0002_appointment_schema
Create Date: 2026-07-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_diagnostic_schema"
down_revision: str | None = "0002_appointment_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "diagnostic_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_call_id", sa.String(length=80), nullable=True),
        sa.Column("customer_name", sa.String(length=160), nullable=True),
        sa.Column("customer_email", sa.String(length=255), nullable=True),
        sa.Column("customer_phone", sa.String(length=32), nullable=True),
        sa.Column("appliance_type", sa.String(length=80), nullable=True),
        sa.Column("symptoms", sa.JSON(), nullable=False),
        sa.Column("zip_code", sa.String(length=10), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("safety_blocked", sa.Boolean(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_diagnostic_sessions_appliance_type"),
        "diagnostic_sessions",
        ["appliance_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_diagnostic_sessions_customer_email"),
        "diagnostic_sessions",
        ["customer_email"],
        unique=False,
    )
    op.create_index(
        op.f("ix_diagnostic_sessions_customer_phone"),
        "diagnostic_sessions",
        ["customer_phone"],
        unique=False,
    )
    op.create_index(
        op.f("ix_diagnostic_sessions_external_call_id"),
        "diagnostic_sessions",
        ["external_call_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_diagnostic_sessions_status"),
        "diagnostic_sessions",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_diagnostic_sessions_zip_code"),
        "diagnostic_sessions",
        ["zip_code"],
        unique=False,
    )

    op.create_table(
        "diagnostic_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=24), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_name", sa.String(length=80), nullable=True),
        sa.Column("tool_payload", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["diagnostic_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_diagnostic_events_role"),
        "diagnostic_events",
        ["role"],
        unique=False,
    )
    op.create_index(
        op.f("ix_diagnostic_events_session_id"),
        "diagnostic_events",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_diagnostic_events_tool_name"),
        "diagnostic_events",
        ["tool_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_diagnostic_events_tool_name"), table_name="diagnostic_events")
    op.drop_index(op.f("ix_diagnostic_events_session_id"), table_name="diagnostic_events")
    op.drop_index(op.f("ix_diagnostic_events_role"), table_name="diagnostic_events")
    op.drop_table("diagnostic_events")
    op.drop_index(op.f("ix_diagnostic_sessions_zip_code"), table_name="diagnostic_sessions")
    op.drop_index(op.f("ix_diagnostic_sessions_status"), table_name="diagnostic_sessions")
    op.drop_index(
        op.f("ix_diagnostic_sessions_external_call_id"),
        table_name="diagnostic_sessions",
    )
    op.drop_index(
        op.f("ix_diagnostic_sessions_customer_phone"),
        table_name="diagnostic_sessions",
    )
    op.drop_index(
        op.f("ix_diagnostic_sessions_customer_email"),
        table_name="diagnostic_sessions",
    )
    op.drop_index(
        op.f("ix_diagnostic_sessions_appliance_type"),
        table_name="diagnostic_sessions",
    )
    op.drop_table("diagnostic_sessions")
