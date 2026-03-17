"""add project_schedules table

Revision ID: g3a4b5c6d7e8
Revises: f2a3b4c5d6e7
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "g3a4b5c6d7e8"
down_revision = "h4i5j6k7l8m9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_schedules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("repo_sync_interval", sa.String(32), nullable=False, server_default="disabled"),
        sa.Column("repo_sync_last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_sync_interval", sa.String(32), nullable=False, server_default="disabled"),
        sa.Column("delivery_sync_last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("security_scan_interval", sa.String(32), nullable=False, server_default="disabled"),
        sa.Column("security_scan_last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dependency_scan_interval", sa.String(32), nullable=False, server_default="disabled"),
        sa.Column("dependency_scan_last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("insights_interval", sa.String(32), nullable=False, server_default="daily"),
        sa.Column("insights_last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        comment="Per-project scheduling configuration controlling how often automated tasks run.",
    )
    op.create_index("ix_project_schedules_project_id", "project_schedules", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_project_schedules_project_id", table_name="project_schedules")
    op.drop_table("project_schedules")
