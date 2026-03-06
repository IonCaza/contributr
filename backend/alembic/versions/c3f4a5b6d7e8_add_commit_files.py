"""add commit_files table

Revision ID: c3f4a5b6d7e8
Revises: a1b2c3d4e5f6
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c3f4a5b6d7e8"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "commit_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("commit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("commits.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("file_path", sa.String(1024), nullable=False, index=True),
        sa.Column("lines_added", sa.Integer(), server_default="0", nullable=False),
        sa.Column("lines_deleted", sa.Integer(), server_default="0", nullable=False),
        sa.UniqueConstraint("commit_id", "file_path", name="uq_commit_file"),
    )


def downgrade() -> None:
    op.drop_table("commit_files")
