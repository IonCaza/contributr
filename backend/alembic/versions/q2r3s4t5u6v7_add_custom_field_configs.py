"""add custom_field_configs table

Revision ID: q2r3s4t5u6v7
Revises: p1q2r3s4t5u6
Create Date: 2026-03-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "q2r3s4t5u6v7"
down_revision = "p1q2r3s4t5u6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "custom_field_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("field_reference_name", sa.String(500), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("field_type", sa.String(50), nullable=False, server_default="string"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "field_reference_name", name="uq_custom_field_project_ref"),
        comment="Per-project configuration of additional platform fields to import during work item sync.",
    )


def downgrade() -> None:
    op.drop_table("custom_field_configs")
