"""add must_change_password column to users

Revision ID: aa1bb2cc3dd4
Revises: b3c4d5e6f7a8
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa

revision = "aa1bb2cc3dd4"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("users", "must_change_password")
