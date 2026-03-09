"""add feedback table

Revision ID: w8x9y0z1a2b3
Revises: v7w8x9y0z1a2
Create Date: 2026-03-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "w8x9y0z1a2b3"
down_revision = "v7w8x9y0z1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source", sa.String(10), nullable=False, comment="Origin of the feedback: agent or human"),
        sa.Column("category", sa.String(100), nullable=True, comment="Classification: capability_gap, missing_data, missing_tool, integration_needed, bug, suggestion, other"),
        sa.Column("content", sa.Text(), nullable=False, comment="Description of the gap or feedback"),
        sa.Column("user_query", sa.Text(), nullable=True, comment="The user's original question that triggered the gap report"),
        sa.Column("agent_slug", sa.String(100), nullable=True, comment="Slug of the agent that reported the gap"),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True, comment="Chat session where the feedback originated"),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="User who submitted the feedback"),
        sa.Column("message_id", UUID(as_uuid=True), sa.ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True, comment="Specific chat message the feedback is about"),
        sa.Column("status", sa.String(10), nullable=False, server_default="new", comment="Review status: new, reviewed, or resolved"),
        sa.Column("admin_notes", sa.Text(), nullable=True, comment="Notes added by an admin when reviewing"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, comment="Timestamp when the feedback was created"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, comment="Timestamp of the last modification"),
        comment="Stores both agent-reported capability gaps and human-submitted feedback.",
    )
    op.create_index("ix_feedback_session_id", "feedback", ["session_id"])
    op.create_index("ix_feedback_user_id", "feedback", ["user_id"])
    op.create_index("ix_feedback_status", "feedback", ["status"])
    op.create_index("ix_feedback_source", "feedback", ["source"])


def downgrade() -> None:
    op.drop_index("ix_feedback_source")
    op.drop_index("ix_feedback_status")
    op.drop_index("ix_feedback_user_id")
    op.drop_index("ix_feedback_session_id")
    op.drop_table("feedback")
