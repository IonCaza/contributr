"""add contributor insight tables

Revision ID: s4t5u6v7w8x9
Revises: r3s4t5u6v7w8
Create Date: 2026-03-07
"""
from alembic import op
import sqlalchemy as sa

revision = "s4t5u6v7w8x9"
down_revision = "r3s4t5u6v7w8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS contributor_insight_runs (
            id UUID PRIMARY KEY,
            contributor_id UUID NOT NULL REFERENCES contributors(id) ON DELETE CASCADE,
            status VARCHAR(20) NOT NULL DEFAULT 'running',
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            finished_at TIMESTAMPTZ,
            findings_count INTEGER NOT NULL DEFAULT 0,
            error_message TEXT
        );
        CREATE INDEX IF NOT EXISTS ix_contributor_insight_runs_contributor_id
            ON contributor_insight_runs (contributor_id);
    """))

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS contributor_insight_findings (
            id UUID PRIMARY KEY,
            run_id UUID NOT NULL REFERENCES contributor_insight_runs(id) ON DELETE CASCADE,
            contributor_id UUID NOT NULL REFERENCES contributors(id) ON DELETE CASCADE,
            category VARCHAR(50) NOT NULL,
            severity VARCHAR(20) NOT NULL,
            slug VARCHAR(200) NOT NULL,
            title VARCHAR(500) NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            recommendation TEXT NOT NULL DEFAULT '',
            metric_data JSONB DEFAULT '{}',
            affected_entities JSONB DEFAULT '{}',
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            first_detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            resolved_at TIMESTAMPTZ,
            dismissed_at TIMESTAMPTZ,
            dismissed_by_id UUID REFERENCES users(id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS ix_contributor_insight_findings_run_id
            ON contributor_insight_findings (run_id);
        CREATE INDEX IF NOT EXISTS ix_contributor_insight_findings_contributor_id
            ON contributor_insight_findings (contributor_id);
        CREATE INDEX IF NOT EXISTS ix_contributor_insight_findings_slug
            ON contributor_insight_findings (slug);
    """))


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS contributor_insight_findings"))
    op.execute(sa.text("DROP TABLE IF EXISTS contributor_insight_runs"))
