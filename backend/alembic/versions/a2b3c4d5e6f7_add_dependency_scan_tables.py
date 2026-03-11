"""add dependency scan tables

Revision ID: a2b3c4d5e6f7
Revises: z1a2b3c4d5e6
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "a2b3c4d5e6f7"
down_revision = "z1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop old VARCHAR-based tables if they exist from a prior run
    op.execute(sa.text("DROP TABLE IF EXISTS dependency_findings"))
    op.execute(sa.text("DROP TABLE IF EXISTS dep_scan_runs"))

    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE depscanstatus AS ENUM ('queued', 'running', 'completed', 'failed');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """))
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE depfindingseverity AS ENUM ('critical', 'high', 'medium', 'low', 'none');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """))
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE depfindingstatus AS ENUM ('active', 'fixed', 'dismissed');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """))

    op.execute(sa.text("""
        CREATE TABLE dep_scan_runs (
            id UUID PRIMARY KEY,
            repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            status depscanstatus NOT NULL DEFAULT 'queued',
            started_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ,
            findings_count INTEGER NOT NULL DEFAULT 0,
            vulnerable_count INTEGER NOT NULL DEFAULT 0,
            outdated_count INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_dep_scan_runs_repository_id ON dep_scan_runs(repository_id);
        CREATE INDEX ix_dep_scan_runs_project_id ON dep_scan_runs(project_id);
    """))

    op.execute(sa.text("""
        CREATE TABLE dependency_findings (
            id UUID PRIMARY KEY,
            scan_run_id UUID NOT NULL REFERENCES dep_scan_runs(id) ON DELETE CASCADE,
            repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            file_path VARCHAR(1024) NOT NULL,
            file_type VARCHAR(100) NOT NULL,
            ecosystem VARCHAR(50) NOT NULL,
            package_name VARCHAR(500) NOT NULL,
            current_version VARCHAR(200),
            latest_version VARCHAR(200),
            is_outdated BOOLEAN NOT NULL DEFAULT false,
            is_vulnerable BOOLEAN NOT NULL DEFAULT false,
            is_direct BOOLEAN NOT NULL DEFAULT true,
            severity depfindingseverity NOT NULL DEFAULT 'none',
            vulnerabilities JSONB DEFAULT '[]',
            license VARCHAR(200),
            status depfindingstatus NOT NULL DEFAULT 'active',
            first_detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            dismissed_at TIMESTAMPTZ,
            dismissed_by_id UUID REFERENCES users(id) ON DELETE SET NULL
        );
        CREATE INDEX ix_dependency_findings_scan_run_id ON dependency_findings(scan_run_id);
        CREATE INDEX ix_dependency_findings_repository_id ON dependency_findings(repository_id);
        CREATE INDEX ix_dependency_findings_project_id ON dependency_findings(project_id);
        CREATE INDEX ix_dependency_findings_file_path ON dependency_findings(file_path);
        CREATE INDEX ix_dependency_findings_ecosystem ON dependency_findings(ecosystem);
        CREATE INDEX ix_dependency_findings_package_name ON dependency_findings(package_name);
    """))


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS dependency_findings"))
    op.execute(sa.text("DROP TABLE IF EXISTS dep_scan_runs"))
    op.execute(sa.text("DROP TYPE IF EXISTS depfindingstatus"))
    op.execute(sa.text("DROP TYPE IF EXISTS depfindingseverity"))
    op.execute(sa.text("DROP TYPE IF EXISTS depscanstatus"))
