"""add sast_ignored_rules table and scan_branches column

Revision ID: v7w8x9y0z1a2
Revises: u6v7w8x9y0z1
Create Date: 2026-03-08
"""
from alembic import op
import sqlalchemy as sa

revision = "v7w8x9y0z1a2"
down_revision = "u6v7w8x9y0z1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("""
        ALTER TABLE sast_rule_profiles
        ADD COLUMN IF NOT EXISTS scan_branches JSONB NOT NULL DEFAULT '[]';
    """))

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS sast_ignored_rules (
            id UUID PRIMARY KEY,
            rule_id VARCHAR(500) NOT NULL,
            repository_id UUID REFERENCES repositories(id) ON DELETE CASCADE,
            reason TEXT NOT NULL DEFAULT '',
            created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS ix_sast_ignored_rules_rule_id ON sast_ignored_rules(rule_id);
        CREATE INDEX IF NOT EXISTS ix_sast_ignored_rules_repository_id ON sast_ignored_rules(repository_id);
    """))


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS sast_ignored_rules"))
    op.execute(sa.text("ALTER TABLE sast_rule_profiles DROP COLUMN IF EXISTS scan_branches"))
