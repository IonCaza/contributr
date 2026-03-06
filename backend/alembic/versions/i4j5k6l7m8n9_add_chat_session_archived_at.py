"""add archived_at column to chat_sessions

Revision ID: i4j5k6l7m8n9
Revises: h3i4j5k6l7m8
Create Date: 2026-03-06
"""
from alembic import op
import sqlalchemy as sa

revision = "i4j5k6l7m8n9"
down_revision = "h3i4j5k6l7m8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("chat_sessions", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("chat_sessions", "archived_at")
