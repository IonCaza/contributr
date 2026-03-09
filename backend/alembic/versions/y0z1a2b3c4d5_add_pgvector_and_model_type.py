"""add pgvector extension and llm_provider model_type

Revision ID: y0z1a2b3c4d5
Revises: x9y0z1a2b3c4
Create Date: 2026-03-09
"""
from alembic import op
import sqlalchemy as sa

revision = "y0z1a2b3c4d5"
down_revision = "x9y0z1a2b3c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column(
        "llm_providers",
        sa.Column(
            "model_type",
            sa.String(20),
            nullable=False,
            server_default="chat",
            comment="Purpose: chat (LLM) or embedding (vector embeddings)",
        ),
    )


def downgrade() -> None:
    op.drop_column("llm_providers", "model_type")
    op.execute("DROP EXTENSION IF EXISTS vector")
