"""add pr_comments table

Revision ID: e1f2a3b4c5d6
Revises: d5e6f7a8b9c0
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "e1f2a3b4c5d6"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pr_comments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("pull_request_id", UUID(as_uuid=True), sa.ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("author_name", sa.String(255), nullable=False),
        sa.Column("author_id", UUID(as_uuid=True), sa.ForeignKey("contributors.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("body", sa.Text, nullable=False, server_default=""),
        sa.Column("thread_id", sa.String(255), nullable=True),
        sa.Column("parent_comment_id", UUID(as_uuid=True), sa.ForeignKey("pr_comments.id", ondelete="CASCADE"), nullable=True),
        sa.Column("file_path", sa.String(1024), nullable=True),
        sa.Column("line_number", sa.Integer, nullable=True),
        sa.Column("comment_type", sa.Enum("INLINE", "GENERAL", "SYSTEM", name="prcommenttype"), nullable=False, server_default="GENERAL"),
        sa.Column("platform_comment_id", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_pr_comments_thread_id", "pr_comments", ["thread_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pr_comments_thread_id", table_name="pr_comments")
    op.drop_table("pr_comments")
    op.execute("DROP TYPE IF EXISTS prcommenttype")
