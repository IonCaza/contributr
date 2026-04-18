"""add project_delivery_settings table

Revision ID: z3a4b5c6d7e8
Revises: y2z3a4b5c6d7
Create Date: 2026-04-17
"""

import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "z3a4b5c6d7e8"
down_revision = "y2z3a4b5c6d7"
branch_labels = None
depends_on = None


_DEFAULT_CYCLE_START = ["Active", "Committed", "In Progress"]
_DEFAULT_CYCLE_END = ["Closed", "Done", "Completed"]
_DEFAULT_REVIEW = ["In Review", "Code Review", "PR Review"]
_DEFAULT_TESTING = ["Testing", "QA", "Verify"]
_DEFAULT_READY = ["Ready", "Approved", "Committed"]

_DEFAULT_THRESHOLDS = {
    "unestimated_pct_warn": 20,
    "unestimated_pct_crit": 40,
    "unassigned_pct_warn": 20,
    "unassigned_pct_crit": 40,
    "stale_days": 30,
    "stale_pct_warn": 15,
    "stale_pct_crit": 30,
    "planning_sprints_min": 1,
    "planning_sprints_target": 2,
    "priority_top_tier_pct_warn": 50,
    "sprint_scope_change_pct_warn": 10,
    "sprint_scope_change_pct_crit": 25,
}


def _array_default(values: list[str]) -> str:
    joined = ",".join(f"'{s}'" for s in values)
    return f"ARRAY[{joined}]::varchar[]"


def _jsonb_default(obj: dict) -> str:
    payload = json.dumps(obj).replace("'", "''")
    return f"'{payload}'::jsonb"


def upgrade() -> None:
    op.create_table(
        "project_delivery_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "cycle_time_start_states",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text(_array_default(_DEFAULT_CYCLE_START)),
        ),
        sa.Column(
            "cycle_time_end_states",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text(_array_default(_DEFAULT_CYCLE_END)),
        ),
        sa.Column(
            "review_states",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text(_array_default(_DEFAULT_REVIEW)),
        ),
        sa.Column(
            "testing_states",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text(_array_default(_DEFAULT_TESTING)),
        ),
        sa.Column(
            "ready_states",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text(_array_default(_DEFAULT_READY)),
        ),
        sa.Column("tshirt_custom_field", sa.String(255), nullable=True),
        sa.Column(
            "backlog_health_thresholds",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text(_jsonb_default(_DEFAULT_THRESHOLDS)),
        ),
        sa.Column("long_running_threshold_days", sa.Integer(), nullable=False, server_default=sa.text("14")),
        sa.Column("rolling_capacity_sprints", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        comment=(
            "Per-project delivery analytics configuration: cycle time state mapping, "
            "backlog health thresholds, ready states, and t-shirt sizing field."
        ),
    )
    op.create_index(
        "ix_project_delivery_settings_project_id",
        "project_delivery_settings",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_project_delivery_settings_project_id",
        table_name="project_delivery_settings",
    )
    op.drop_table("project_delivery_settings")
