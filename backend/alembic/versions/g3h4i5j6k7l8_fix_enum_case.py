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


def _safe_rename(type_name: str, old: str, new: str) -> None:
    op.execute(
        f"DO $$ BEGIN "
        f"IF EXISTS (SELECT 1 FROM pg_enum WHERE enumtypid = '{type_name}'::regtype AND enumlabel = '{old}') "
        f"THEN EXECUTE 'ALTER TYPE {type_name} RENAME VALUE ''{old}'' TO ''{new}'''; "
        f"END IF; "
        f"END $$;"
    )


def upgrade() -> None:
    _safe_rename("prcommenttype", "inline", "INLINE")
    _safe_rename("prcommenttype", "general", "GENERAL")
    _safe_rename("prcommenttype", "system", "SYSTEM")
    op.execute("ALTER TABLE pr_comments ALTER COLUMN comment_type SET DEFAULT 'GENERAL'")

    _safe_rename("adrstatus", "proposed", "PROPOSED")
    _safe_rename("adrstatus", "accepted", "ACCEPTED")
    _safe_rename("adrstatus", "deprecated", "DEPRECATED")
    _safe_rename("adrstatus", "superseded", "SUPERSEDED")
    _safe_rename("adrstatus", "rejected", "REJECTED")
    op.execute("ALTER TABLE adrs ALTER COLUMN status SET DEFAULT 'PROPOSED'")


def downgrade() -> None:
    op.execute("ALTER TABLE adrs ALTER COLUMN status SET DEFAULT 'proposed'")
    _safe_rename("adrstatus", "REJECTED", "rejected")
    _safe_rename("adrstatus", "SUPERSEDED", "superseded")
    _safe_rename("adrstatus", "DEPRECATED", "deprecated")
    _safe_rename("adrstatus", "ACCEPTED", "accepted")
    _safe_rename("adrstatus", "PROPOSED", "proposed")

    op.execute("ALTER TABLE pr_comments ALTER COLUMN comment_type SET DEFAULT 'general'")
    _safe_rename("prcommenttype", "SYSTEM", "system")
    _safe_rename("prcommenttype", "GENERAL", "general")
    _safe_rename("prcommenttype", "INLINE", "inline")
