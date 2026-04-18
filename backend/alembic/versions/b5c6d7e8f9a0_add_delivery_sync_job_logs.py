"""add logs column to delivery_sync_jobs for historical log retrieval

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
Create Date: 2026-04-17

Adds a ``logs`` JSONB column on ``delivery_sync_jobs`` so we can persist the
full log stream once a sync completes. Until now logs lived only in Redis
under a project-scoped key, which caused three problems:

* Every sync job for the same project wrote to the same list, so clicking
  "Logs" on job N showed logs concatenated from prior runs.
* After the 1h Redis TTL (or a Redis restart) logs were gone entirely.
* Historical jobs could never be inspected from the UI.

The worker now keys the live log stream on ``job_id`` and, on completion or
failure, snapshots the Redis list into this column. The ``/sync/logs``
endpoint prefers the live Redis stream when available and falls back to this
persisted array for terminal jobs.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "b5c6d7e8f9a0"
down_revision = "a4b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "delivery_sync_jobs",
        sa.Column("logs", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("delivery_sync_jobs", "logs")
