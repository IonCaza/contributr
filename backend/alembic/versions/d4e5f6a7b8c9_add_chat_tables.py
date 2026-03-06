"""add chat_sessions and chat_messages tables

Revision ID: d4e5f6a7b8c9
Revises: c3f4a5b6d7e8
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d4e5f6a7b8c9"
down_revision = "c3f4a5b6d7e8"
branch_labels = None
depends_on = None

message_role_enum = postgresql.ENUM("user", "assistant", "tool", name="messagerole", create_type=False)


def upgrade():
    message_role_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(255), server_default="New chat"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("role", message_role_enum, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    message_role_enum.drop(op.get_bind(), checkfirst=True)
