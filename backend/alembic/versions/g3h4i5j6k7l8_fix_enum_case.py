"""fix prcommenttype and adrstatus enum value casing

Revision ID: g3h4i5j6k7l8
Revises: f2a3b4c5d6e7
Create Date: 2026-03-05
"""
from alembic import op

revision = "g3h4i5j6k7l8"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE prcommenttype RENAME VALUE 'inline' TO 'INLINE'")
    op.execute("ALTER TYPE prcommenttype RENAME VALUE 'general' TO 'GENERAL'")
    op.execute("ALTER TYPE prcommenttype RENAME VALUE 'system' TO 'SYSTEM'")
    op.execute("ALTER TABLE pr_comments ALTER COLUMN comment_type SET DEFAULT 'GENERAL'")

    op.execute("ALTER TYPE adrstatus RENAME VALUE 'proposed' TO 'PROPOSED'")
    op.execute("ALTER TYPE adrstatus RENAME VALUE 'accepted' TO 'ACCEPTED'")
    op.execute("ALTER TYPE adrstatus RENAME VALUE 'deprecated' TO 'DEPRECATED'")
    op.execute("ALTER TYPE adrstatus RENAME VALUE 'superseded' TO 'SUPERSEDED'")
    op.execute("ALTER TYPE adrstatus RENAME VALUE 'rejected' TO 'REJECTED'")
    op.execute("ALTER TABLE adrs ALTER COLUMN status SET DEFAULT 'PROPOSED'")


def downgrade() -> None:
    op.execute("ALTER TABLE adrs ALTER COLUMN status SET DEFAULT 'proposed'")
    op.execute("ALTER TYPE adrstatus RENAME VALUE 'REJECTED' TO 'rejected'")
    op.execute("ALTER TYPE adrstatus RENAME VALUE 'SUPERSEDED' TO 'superseded'")
    op.execute("ALTER TYPE adrstatus RENAME VALUE 'DEPRECATED' TO 'deprecated'")
    op.execute("ALTER TYPE adrstatus RENAME VALUE 'ACCEPTED' TO 'accepted'")
    op.execute("ALTER TYPE adrstatus RENAME VALUE 'PROPOSED' TO 'proposed'")

    op.execute("ALTER TABLE pr_comments ALTER COLUMN comment_type SET DEFAULT 'general'")
    op.execute("ALTER TYPE prcommenttype RENAME VALUE 'SYSTEM' TO 'system'")
    op.execute("ALTER TYPE prcommenttype RENAME VALUE 'GENERAL' TO 'general'")
    op.execute("ALTER TYPE prcommenttype RENAME VALUE 'INLINE' TO 'inline'")
