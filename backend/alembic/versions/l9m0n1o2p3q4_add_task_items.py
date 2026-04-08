"""add task_items table for structured task decomposition

Revision ID: l9m0n1o2p3q4
Revises: k8l9m0n1o2p3
Create Date: 2026-04-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID

revision = "l9m0n1o2p3q4"
down_revision = "k8l9m0n1o2p3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS task_items")
    op.create_table(
        "task_items",
        sa.Column("id", sa.String(8), nullable=False, comment="Session-scoped sequential ID (e.g. t1, t2)"),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, comment="Chat session this task belongs to"),
        sa.Column("subject", sa.String(200), nullable=False, comment="Short title describing the task"),
        sa.Column("description", sa.Text, nullable=True, comment="Detailed description with specifics"),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False, comment="Current status: pending, in_progress, completed, blocked, cancelled"),
        sa.Column("owner_agent_slug", sa.String(100), nullable=True, comment="Agent slug assigned to this task"),
        sa.Column("blocked_by", ARRAY(sa.String), server_default="{}", comment="Task IDs that must complete before this one"),
        sa.Column("blocks", ARRAY(sa.String), server_default="{}", comment="Task IDs that depend on this one"),
        sa.Column("metadata", JSON, server_default="{}", comment="Arbitrary metadata for extensions"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, comment="Creation timestamp"),
        sa.PrimaryKeyConstraint("id", "session_id"),
        sa.CheckConstraint(
            "status IN ('pending','in_progress','completed','blocked','cancelled')",
            name="ck_task_items_status",
        ),
        comment="Structured task decomposition items scoped to a chat session.",
    )
    op.create_index("ix_task_items_session_id", "task_items", ["session_id"])


def downgrade() -> None:
    op.drop_table("task_items")
