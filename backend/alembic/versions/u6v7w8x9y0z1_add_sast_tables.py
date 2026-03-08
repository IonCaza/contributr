"""add sast_rule_profiles, sast_scan_runs, and sast_findings tables

Revision ID: u6v7w8x9y0z1
Revises: t5u6v7w8x9y0
Create Date: 2026-03-08
"""
from alembic import op
import sqlalchemy as sa

revision = "u6v7w8x9y0z1"
down_revision = "t5u6v7w8x9y0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE sastscanstatus AS ENUM ('queued', 'running', 'completed', 'failed');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """))
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE sastseverity AS ENUM ('critical', 'high', 'medium', 'low', 'info');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """))
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE sastconfidence AS ENUM ('high', 'medium', 'low');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """))
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE sastfindingstatus AS ENUM ('open', 'fixed', 'dismissed', 'false_positive');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """))

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS sast_rule_profiles (
            id UUID PRIMARY KEY,
            name VARCHAR(200) NOT NULL UNIQUE,
            description TEXT NOT NULL DEFAULT '',
            rulesets JSONB NOT NULL DEFAULT '["auto"]',
            custom_rules_yaml TEXT,
            is_default BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """))

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS sast_scan_runs (
            id UUID PRIMARY KEY,
            repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            status sastscanstatus NOT NULL DEFAULT 'queued',
            branch VARCHAR(500),
            commit_sha VARCHAR(40),
            tool VARCHAR(50) NOT NULL DEFAULT 'semgrep',
            config_profile_id UUID REFERENCES sast_rule_profiles(id) ON DELETE SET NULL,
            started_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ,
            findings_count INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS ix_sast_scan_runs_repository_id ON sast_scan_runs(repository_id);
        CREATE INDEX IF NOT EXISTS ix_sast_scan_runs_project_id ON sast_scan_runs(project_id);
    """))

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS sast_findings (
            id UUID PRIMARY KEY,
            scan_run_id UUID NOT NULL REFERENCES sast_scan_runs(id) ON DELETE CASCADE,
            repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            rule_id VARCHAR(500) NOT NULL,
            severity sastseverity NOT NULL,
            confidence sastconfidence NOT NULL DEFAULT 'medium',
            file_path VARCHAR(1024) NOT NULL,
            start_line INTEGER NOT NULL,
            end_line INTEGER NOT NULL,
            start_col INTEGER,
            end_col INTEGER,
            message TEXT NOT NULL,
            code_snippet TEXT,
            fix_suggestion TEXT,
            cwe_ids JSONB DEFAULT '[]',
            owasp_ids JSONB DEFAULT '[]',
            metadata JSONB DEFAULT '{}',
            status sastfindingstatus NOT NULL DEFAULT 'open',
            first_detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            dismissed_at TIMESTAMPTZ,
            dismissed_by_id UUID REFERENCES users(id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS ix_sast_findings_scan_run_id ON sast_findings(scan_run_id);
        CREATE INDEX IF NOT EXISTS ix_sast_findings_repository_id ON sast_findings(repository_id);
        CREATE INDEX IF NOT EXISTS ix_sast_findings_project_id ON sast_findings(project_id);
        CREATE INDEX IF NOT EXISTS ix_sast_findings_rule_id ON sast_findings(rule_id);
        CREATE INDEX IF NOT EXISTS ix_sast_findings_file_path ON sast_findings(file_path);
    """))


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS sast_findings"))
    op.execute(sa.text("DROP TABLE IF EXISTS sast_scan_runs"))
    op.execute(sa.text("DROP TABLE IF EXISTS sast_rule_profiles"))
    op.execute(sa.text("DROP TYPE IF EXISTS sastfindingstatus"))
    op.execute(sa.text("DROP TYPE IF EXISTS sastconfidence"))
    op.execute(sa.text("DROP TYPE IF EXISTS sastseverity"))
    op.execute(sa.text("DROP TYPE IF EXISTS sastscanstatus"))
