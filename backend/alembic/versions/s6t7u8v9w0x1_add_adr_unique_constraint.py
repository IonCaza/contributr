"""Add unique constraint on (project_id, adr_number) to adrs table.

Revision ID: s6t7u8v9w0x1
Revises: r5s6t7u8v9w0
Create Date: 2026-04-10
"""
from alembic import op

revision = "s6t7u8v9w0x1"
down_revision = "r5s6t7u8v9w0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DELETE FROM adrs a
        USING adrs b
        WHERE a.project_id = b.project_id
          AND a.adr_number = b.adr_number
          AND a.created_at > b.created_at
    """)
    op.create_unique_constraint(
        "uq_adrs_project_number", "adrs", ["project_id", "adr_number"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_adrs_project_number", "adrs", type_="unique")
