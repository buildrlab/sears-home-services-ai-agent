"""Create image upload schema.

Revision ID: 0005_image_upload_schema
Revises: 0004_call_session_schema
Create Date: 2026-07-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_image_upload_schema"
down_revision: str | None = "0004_call_session_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "image_uploads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("diagnostic_session_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("storage_bucket", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=80), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("analysis_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("analysis_summary", sa.Text(), nullable=True),
        sa.Column("analysis_result", sa.JSON(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
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
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_image_uploads_content_type"),
        "image_uploads",
        ["content_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_image_uploads_diagnostic_session_id"),
        "image_uploads",
        ["diagnostic_session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_image_uploads_status"),
        "image_uploads",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_image_uploads_token_hash"),
        "image_uploads",
        ["token_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_image_uploads_token_hash"), table_name="image_uploads")
    op.drop_index(op.f("ix_image_uploads_status"), table_name="image_uploads")
    op.drop_index(op.f("ix_image_uploads_diagnostic_session_id"), table_name="image_uploads")
    op.drop_index(op.f("ix_image_uploads_content_type"), table_name="image_uploads")
    op.drop_table("image_uploads")
