"""add email_mfa_enabled to users (merge heads)

Revision ID: c4d5e6f7a8b9
Revises: aa1bb2cc3dd4, e5f6a7b8c9d0
Create Date: 2026-03-14
"""
from alembic import op
import sqlalchemy as sa

revision = "c4d5e6f7a8b9"
down_revision = ("aa1bb2cc3dd4", "e5f6a7b8c9d0")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    # Backfill: users whose mfa_method is 'email' already have email MFA enrolled
    op.execute("UPDATE users SET email_mfa_enabled = true WHERE mfa_method = 'email'")


def downgrade() -> None:
    op.drop_column("users", "email_mfa_enabled")
