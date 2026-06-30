"""Create technician reference schema.

Revision ID: 0001_technician_schema
Revises:
Create Date: 2026-07-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_technician_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "technicians",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_technicians_email"), "technicians", ["email"], unique=True)

    op.create_table(
        "technician_service_areas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("technician_id", sa.Integer(), nullable=False),
        sa.Column("zip_code", sa.String(length=10), nullable=False),
        sa.ForeignKeyConstraint(["technician_id"], ["technicians.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "technician_id",
            "zip_code",
            name="uq_service_area_technician_zip",
        ),
    )
    op.create_index(
        op.f("ix_technician_service_areas_technician_id"),
        "technician_service_areas",
        ["technician_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_technician_service_areas_zip_code"),
        "technician_service_areas",
        ["zip_code"],
        unique=False,
    )

    op.create_table(
        "technician_specialties",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("technician_id", sa.Integer(), nullable=False),
        sa.Column("appliance_type", sa.String(length=80), nullable=False),
        sa.ForeignKeyConstraint(["technician_id"], ["technicians.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "technician_id",
            "appliance_type",
            name="uq_specialty_technician_appliance",
        ),
    )
    op.create_index(
        op.f("ix_technician_specialties_appliance_type"),
        "technician_specialties",
        ["appliance_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_technician_specialties_technician_id"),
        "technician_specialties",
        ["technician_id"],
        unique=False,
    )

    op.create_table(
        "availability_slots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("technician_id", sa.Integer(), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["technician_id"], ["technicians.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "technician_id",
            "day_of_week",
            "start_time",
            "end_time",
            name="uq_availability_technician_window",
        ),
    )
    op.create_index(
        op.f("ix_availability_slots_technician_id"),
        "availability_slots",
        ["technician_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_availability_slots_technician_id"), table_name="availability_slots")
    op.drop_table("availability_slots")
    op.drop_index(
        op.f("ix_technician_specialties_technician_id"),
        table_name="technician_specialties",
    )
    op.drop_index(
        op.f("ix_technician_specialties_appliance_type"),
        table_name="technician_specialties",
    )
    op.drop_table("technician_specialties")
    op.drop_index(
        op.f("ix_technician_service_areas_zip_code"),
        table_name="technician_service_areas",
    )
    op.drop_index(
        op.f("ix_technician_service_areas_technician_id"),
        table_name="technician_service_areas",
    )
    op.drop_table("technician_service_areas")
    op.drop_index(op.f("ix_technicians_email"), table_name="technicians")
    op.drop_table("technicians")
