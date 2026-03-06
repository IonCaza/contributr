"""add context management columns

Revision ID: k6l7m8n9o0p1
Revises: j5k6l7m8n9o0
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa

revision = "k6l7m8n9o0p1"
down_revision = "j5k6l7m8n9o0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("llm_providers", sa.Column("context_window", sa.Integer(), nullable=True))
    op.add_column("agents", sa.Column("summary_token_limit", sa.Integer(), nullable=True))
    op.add_column("chat_sessions", sa.Column("context_summary", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_sessions", "context_summary")
    op.drop_column("agents", "summary_token_limit")
    op.drop_column("llm_providers", "context_window")
