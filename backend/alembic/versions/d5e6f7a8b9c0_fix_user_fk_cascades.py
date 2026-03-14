"""fix user FK cascades for ssh_credentials and platform_credentials

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-03-14
"""
from alembic import op
import sqlalchemy as sa

revision = "d5e6f7a8b9c0"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ssh_credentials: CASCADE delete when user is deleted
    op.drop_constraint("ssh_credentials_created_by_id_fkey", "ssh_credentials", type_="foreignkey")
    op.create_foreign_key(
        "ssh_credentials_created_by_id_fkey", "ssh_credentials",
        "users", ["created_by_id"], ["id"], ondelete="CASCADE",
    )

    # platform_credentials: SET NULL when user is deleted (shared system resource)
    op.drop_constraint("platform_credentials_created_by_id_fkey", "platform_credentials", type_="foreignkey")
    op.alter_column("platform_credentials", "created_by_id", nullable=True)
    op.create_foreign_key(
        "platform_credentials_created_by_id_fkey", "platform_credentials",
        "users", ["created_by_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("platform_credentials_created_by_id_fkey", "platform_credentials", type_="foreignkey")
    op.alter_column("platform_credentials", "created_by_id", nullable=False)
    op.create_foreign_key(
        "platform_credentials_created_by_id_fkey", "platform_credentials",
        "users", ["created_by_id"], ["id"],
    )

    op.drop_constraint("ssh_credentials_created_by_id_fkey", "ssh_credentials", type_="foreignkey")
    op.create_foreign_key(
        "ssh_credentials_created_by_id_fkey", "ssh_credentials",
        "users", ["created_by_id"], ["id"],
    )
