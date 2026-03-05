"""fix syncstatus enum values to lowercase

Revision ID: a1b2c3d4e5f6
Revises: bfac52d26469
Create Date: 2026-03-04 19:05:00.000000
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "bfac52d26469"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RENAMES = [
    ("QUEUED", "queued"),
    ("RUNNING", "running"),
    ("COMPLETED", "completed"),
    ("FAILED", "failed"),
]


def upgrade() -> None:
    conn = op.get_bind()
    existing = {
        row[0]
        for row in conn.execute(
            text("SELECT enumlabel FROM pg_enum WHERE enumtypid = 'syncstatus'::regtype")
        )
    }
    for old, new in RENAMES:
        if old in existing:
            op.execute(f"ALTER TYPE syncstatus RENAME VALUE '{old}' TO '{new}'")


def downgrade() -> None:
    conn = op.get_bind()
    existing = {
        row[0]
        for row in conn.execute(
            text("SELECT enumlabel FROM pg_enum WHERE enumtypid = 'syncstatus'::regtype")
        )
    }
    for old, new in RENAMES:
        if new in existing:
            op.execute(f"ALTER TYPE syncstatus RENAME VALUE '{new}' TO '{old}'")
