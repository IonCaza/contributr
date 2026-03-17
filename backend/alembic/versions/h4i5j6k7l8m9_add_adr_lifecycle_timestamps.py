"""add committed_to_repo_at and removed_from_repo_at to adrs

Revision ID: h4i5j6k7l8m9
Revises: g3h4i5j6k7l8
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = "h4i5j6k7l8m9"
down_revision = "g3h4i5j6k7l8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("adrs", sa.Column("committed_to_repo_at", sa.DateTime(timezone=True), nullable=True,
                                     comment="When this ADR was first committed to the git repository"))
    op.add_column("adrs", sa.Column("removed_from_repo_at", sa.DateTime(timezone=True), nullable=True,
                                     comment="When sync detected this ADR was removed from the repository"))

    op.execute(
        "UPDATE adrs SET committed_to_repo_at = created_at "
        "WHERE file_path IS NOT NULL AND committed_to_repo_at IS NULL"
    )


def downgrade() -> None:
    op.drop_column("adrs", "removed_from_repo_at")
    op.drop_column("adrs", "committed_to_repo_at")
