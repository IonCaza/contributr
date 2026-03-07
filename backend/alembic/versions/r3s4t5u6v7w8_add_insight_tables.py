"""add insight_runs and insight_findings tables

Revision ID: r3s4t5u6v7w8
Revises: q2r3s4t5u6v7
Create Date: 2026-03-07
"""
from alembic import op
import sqlalchemy as sa

revision = "r3s4t5u6v7w8"
down_revision = "q2r3s4t5u6v7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE insightrunstatus AS ENUM ('running', 'completed', 'failed');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """))
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE insightseverity AS ENUM ('critical', 'warning', 'info');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """))
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE insightcategory AS ENUM ('process', 'delivery', 'team_balance', 'code_quality', 'intersection');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """))
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE insightstatus AS ENUM ('active', 'resolved', 'dismissed');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """))

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS insight_runs (
            id UUID PRIMARY KEY,
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            status insightrunstatus NOT NULL DEFAULT 'running',
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            finished_at TIMESTAMPTZ,
            findings_count INTEGER NOT NULL DEFAULT 0,
            error_message TEXT
        );
        CREATE INDEX IF NOT EXISTS ix_insight_runs_project_id ON insight_runs(project_id);
        COMMENT ON TABLE insight_runs IS 'Record of each insights analysis run for a project.';
    """))

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS insight_findings (
            id UUID PRIMARY KEY,
            run_id UUID NOT NULL REFERENCES insight_runs(id) ON DELETE CASCADE,
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            category insightcategory NOT NULL,
            severity insightseverity NOT NULL,
            slug VARCHAR(200) NOT NULL,
            title VARCHAR(500) NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            recommendation TEXT NOT NULL DEFAULT '',
            metric_data JSONB DEFAULT '{}',
            affected_entities JSONB DEFAULT '{}',
            status insightstatus NOT NULL DEFAULT 'active',
            first_detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            resolved_at TIMESTAMPTZ,
            dismissed_at TIMESTAMPTZ,
            dismissed_by_id UUID REFERENCES users(id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS ix_insight_findings_run_id ON insight_findings(run_id);
        CREATE INDEX IF NOT EXISTS ix_insight_findings_project_id ON insight_findings(project_id);
        CREATE INDEX IF NOT EXISTS ix_insight_findings_slug ON insight_findings(slug);
        COMMENT ON TABLE insight_findings IS 'Individual insight finding detected during analysis, tracked by slug for deduplication.';
    """))


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS insight_findings"))
    op.execute(sa.text("DROP TABLE IF EXISTS insight_runs"))
    op.execute(sa.text("DROP TYPE IF EXISTS insightstatus"))
    op.execute(sa.text("DROP TYPE IF EXISTS insightcategory"))
    op.execute(sa.text("DROP TYPE IF EXISTS insightseverity"))
    op.execute(sa.text("DROP TYPE IF EXISTS insightrunstatus"))
