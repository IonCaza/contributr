"""add code_review_runs table

Revision ID: x1y2z3a4b5c6
Revises: w0x1y2z3a4b5
Create Date: 2026-04-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "x1y2z3a4b5c6"
down_revision = "w0x1y2z3a4b5"
branch_labels = None
depends_on = None

_trigger_enum = postgresql.ENUM("webhook", "manual", "scheduled", name="codereviewtrigger", create_type=False)
_status_enum = postgresql.ENUM("queued", "running", "completed", "failed", name="codereviewstatus", create_type=False)
_verdict_enum = postgresql.ENUM("approve", "request_changes", "comment", name="codereviewverdict", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    _trigger_enum.create(bind, checkfirst=True)
    _status_enum.create(bind, checkfirst=True)
    _verdict_enum.create(bind, checkfirst=True)

    op.create_table(
        "code_review_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("pull_request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pull_requests.id", ondelete="SET NULL"), nullable=True),
        sa.Column("platform_pr_number", sa.Integer(), nullable=False),
        sa.Column("trigger", _trigger_enum, nullable=False),
        sa.Column("status", _status_enum, nullable=False, server_default="queued"),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("findings_count", sa.Integer(), nullable=True),
        sa.Column("verdict", _verdict_enum, nullable=True),
        sa.Column("review_url", sa.String(1000), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        comment="Tracks automated code review jobs triggered by webhooks or manual API calls.",
    )


def downgrade() -> None:
    op.drop_table("code_review_runs")
    bind = op.get_bind()
    _verdict_enum.drop(bind, checkfirst=True)
    _status_enum.drop(bind, checkfirst=True)
    _trigger_enum.drop(bind, checkfirst=True)
