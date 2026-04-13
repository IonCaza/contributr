"""Add delegation_query column to agent_activities table.

Revision ID: t7u8v9w0x1y2
Revises: s6t7u8v9w0x1
Create Date: 2026-04-10
"""
import sqlalchemy as sa
from alembic import op

revision = "t7u8v9w0x1y2"
down_revision = "s6t7u8v9w0x1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_activities",
        sa.Column(
            "delegation_query",
            sa.Text(),
            nullable=False,
            server_default="",
            comment="The query the supervisor sent to the child agent",
        ),
    )


def downgrade() -> None:
    op.drop_column("agent_activities", "delegation_query")
