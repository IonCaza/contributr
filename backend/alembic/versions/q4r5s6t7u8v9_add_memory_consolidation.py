"""Add last_memory_consolidation to users.

Revision ID: q4r5s6t7u8v9
Revises: p3q4r5s6t7u8
"""

from alembic import op
import sqlalchemy as sa

revision = "q4r5s6t7u8v9"
down_revision = "p3q4r5s6t7u8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("last_memory_consolidation", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "last_memory_consolidation")
