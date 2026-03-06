"""add platform_credentials and expanded PR fields

Revision ID: g2h3i4j5k6l7
Revises: f1a2b3c4d5e6
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "g2h3i4j5k6l7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "platform_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("token_encrypted", sa.String(4096), nullable=False),
        sa.Column("base_url", sa.String(2048), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.add_column("projects", sa.Column(
        "platform_credential_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("platform_credentials.id", ondelete="SET NULL"),
        nullable=True,
    ))

    op.add_column("pull_requests", sa.Column("comment_count", sa.SmallInteger, server_default="0", nullable=False))
    op.add_column("pull_requests", sa.Column("iteration_count", sa.SmallInteger, server_default="0", nullable=False))
    op.add_column("pull_requests", sa.Column("first_review_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("reviews", sa.Column("comment_count", sa.SmallInteger, server_default="0", nullable=False))

    op.add_column("daily_contributor_stats", sa.Column("pr_comments", sa.Integer, server_default="0", nullable=False))


def downgrade():
    op.drop_column("daily_contributor_stats", "pr_comments")
    op.drop_column("reviews", "comment_count")
    op.drop_column("pull_requests", "first_review_at")
    op.drop_column("pull_requests", "iteration_count")
    op.drop_column("pull_requests", "comment_count")
    op.drop_column("projects", "platform_credential_id")
    op.drop_table("platform_credentials")
