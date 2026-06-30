"""Create customer and appointment schema.

Revision ID: 0002_appointment_schema
Revises: 0001_technician_schema
Create Date: 2026-07-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_appointment_schema"
down_revision: str | None = "0001_technician_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("full_name", sa.String(length=160), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_customers_email"), "customers", ["email"], unique=False)
    op.create_index(op.f("ix_customers_phone"), "customers", ["phone"], unique=False)

    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("technician_id", sa.Integer(), nullable=False),
        sa.Column("appliance_type", sa.String(length=80), nullable=False),
        sa.Column("zip_code", sa.String(length=10), nullable=False),
        sa.Column("issue_summary", sa.Text(), nullable=True),
        sa.Column("scheduled_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("hold_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_slot_key", sa.String(length=160), nullable=True),
        sa.Column("confirmation_code", sa.String(length=32), nullable=True),
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
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["technician_id"], ["technicians.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_appointments_active_slot_key"),
        "appointments",
        ["active_slot_key"],
        unique=True,
    )
    op.create_index(
        op.f("ix_appointments_appliance_type"),
        "appointments",
        ["appliance_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_appointments_confirmation_code"),
        "appointments",
        ["confirmation_code"],
        unique=True,
    )
    op.create_index(
        op.f("ix_appointments_customer_id"),
        "appointments",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_appointments_status"),
        "appointments",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_appointments_technician_id"),
        "appointments",
        ["technician_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_appointments_zip_code"),
        "appointments",
        ["zip_code"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_appointments_zip_code"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_technician_id"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_status"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_customer_id"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_confirmation_code"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_appliance_type"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_active_slot_key"), table_name="appointments")
    op.drop_table("appointments")
    op.drop_index(op.f("ix_customers_phone"), table_name="customers")
    op.drop_index(op.f("ix_customers_email"), table_name="customers")
    op.drop_table("customers")
