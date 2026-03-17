"""add work_item draft_description column

Revision ID: b4c5d6e7f8a9
Revises: g3a4b5c6d7e8
Create Date: 2026-03-14
"""
from alembic import op
import sqlalchemy as sa

revision = "b4c5d6e7f8a9"
down_revision = "g3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "work_items",
        sa.Column(
            "draft_description",
            sa.Text(),
            nullable=True,
            comment="Agent-proposed description awaiting user review. Cleared on accept or discard.",
        ),
    )


def downgrade() -> None:
    op.drop_column("work_items", "draft_description")
