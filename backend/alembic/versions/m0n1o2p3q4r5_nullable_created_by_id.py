"""make presentations.created_by_id nullable

Revision ID: m0n1o2p3q4r5
Revises: l9m0n1o2p3q4
Create Date: 2026-04-01
"""
from alembic import op
import sqlalchemy as sa

revision = "m0n1o2p3q4r5"
down_revision = "l9m0n1o2p3q4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("presentations", "created_by_id", existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    op.alter_column("presentations", "created_by_id", existing_type=sa.UUID(), nullable=False)
