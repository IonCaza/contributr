"""add work_item_activities table

Revision ID: z1a2b3c4d5e6
Revises: y0z1a2b3c4d5
Create Date: 2026-03-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "z1a2b3c4d5e6"
down_revision = "y0z1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "work_item_activities",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("work_item_id", UUID(as_uuid=True), sa.ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("contributor_id", UUID(as_uuid=True), sa.ForeignKey("contributors.id"), nullable=True, index=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("field_name", sa.String(255), nullable=True),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("activity_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.UniqueConstraint("work_item_id", "revision_number", name="uq_work_item_activity_revision"),
        comment="Individual revision/update on a work item, imported from the platform audit trail. "
                "Each row represents a single field change within a revision.",
    )

    comments = {
        "id": "Auto-generated unique identifier",
        "work_item_id": "Work item this activity belongs to",
        "contributor_id": "Contributor who made the change (null if system/unknown)",
        "action": "High-level action: created, state_changed, assigned, field_changed, commented",
        "field_name": "Platform field reference that was changed (e.g. System.State)",
        "old_value": "Previous value (truncated to 2 KB)",
        "new_value": "New value after the change (truncated to 2 KB)",
        "revision_number": "Platform revision/version number for dedup across re-syncs",
        "activity_at": "Timestamp of the activity on the source platform",
    }
    for col, cmt in comments.items():
        escaped = cmt.replace("'", "''")
        op.execute(f"COMMENT ON COLUMN work_item_activities.{col} IS '{escaped}'")


def downgrade() -> None:
    op.drop_table("work_item_activities")
