"""relax work_item_activity unique constraint to allow multi-field revisions

Revision ID: a4b5c6d7e8f9
Revises: z3a4b5c6d7e8
Create Date: 2026-04-17

Extends the unique constraint on ``work_item_activities`` from
``(work_item_id, revision_number)`` to ``(work_item_id, revision_number, field_name)``.

This enables us to record every field that changes in a single revision
(most importantly, ``System.IterationPath`` changes that used to be hidden
behind state/assignment changes), which is required for carry-over analytics.

``field_name`` is nullable, so the constraint uses ``COALESCE('')`` via a
unique index on ``work_item_id, revision_number, COALESCE(field_name, '')``.
"""
from alembic import op

revision = "a4b5c6d7e8f9"
down_revision = "z3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_work_item_activity_revision",
        "work_item_activities",
        type_="unique",
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_work_item_activity_revision_field "
        "ON work_item_activities (work_item_id, revision_number, COALESCE(field_name, ''))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_work_item_activity_revision_field")
    op.create_unique_constraint(
        "uq_work_item_activity_revision",
        "work_item_activities",
        ["work_item_id", "revision_number"],
    )
