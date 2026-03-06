"""add ai_settings table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("model", sa.String(255), nullable=False, server_default="gpt-4o-mini"),
        sa.Column("api_key_encrypted", sa.String(2048), nullable=True),
        sa.Column("base_url", sa.String(2048), nullable=True),
        sa.Column("temperature", sa.Float, nullable=False, server_default="0.1"),
        sa.Column("max_iterations", sa.Integer, nullable=False, server_default="10"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("ai_settings")
