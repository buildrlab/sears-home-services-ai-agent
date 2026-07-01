"""Create call session schema.

Revision ID: 0004_call_session_schema
Revises: 0003_diagnostic_schema
Create Date: 2026-07-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_call_session_schema"
down_revision: str | None = "0003_diagnostic_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "call_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("diagnostic_session_id", sa.Integer(), nullable=True),
        sa.Column("call_sid", sa.String(length=80), nullable=False),
        sa.Column("from_number", sa.String(length=32), nullable=True),
        sa.Column("to_number", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("voice_mode", sa.String(length=32), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["diagnostic_session_id"],
            ["diagnostic_sessions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_call_sessions_call_sid"),
        "call_sessions",
        ["call_sid"],
        unique=True,
    )
    op.create_index(
        op.f("ix_call_sessions_diagnostic_session_id"),
        "call_sessions",
        ["diagnostic_session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_call_sessions_status"),
        "call_sessions",
        ["status"],
        unique=False,
    )

    op.create_table(
        "call_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("call_session_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["call_session_id"], ["call_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_call_events_call_session_id"),
        "call_events",
        ["call_session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_call_events_event_type"),
        "call_events",
        ["event_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_call_events_event_type"), table_name="call_events")
    op.drop_index(op.f("ix_call_events_call_session_id"), table_name="call_events")
    op.drop_table("call_events")
    op.drop_index(op.f("ix_call_sessions_status"), table_name="call_sessions")
    op.drop_index(
        op.f("ix_call_sessions_diagnostic_session_id"),
        table_name="call_sessions",
    )
    op.drop_index(op.f("ix_call_sessions_call_sid"), table_name="call_sessions")
    op.drop_table("call_sessions")
