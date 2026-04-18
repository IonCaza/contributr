"""Per-project delivery analytics configuration.

Controls how cycle time is measured, what states count as "ready"
for backlog health, t-shirt sizing field mapping, and health thresholds.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


DEFAULT_CYCLE_START_STATES = ["Active", "Committed", "In Progress"]
DEFAULT_CYCLE_END_STATES = ["Closed", "Done", "Completed"]
DEFAULT_REVIEW_STATES = ["In Review", "Code Review", "PR Review"]
DEFAULT_TESTING_STATES = ["Testing", "QA", "Verify"]
DEFAULT_READY_STATES = ["Ready", "Approved", "Committed"]

DEFAULT_HEALTH_THRESHOLDS = {
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


class ProjectDeliverySettings(Base):
    """Singleton-per-project settings controlling delivery analytics."""
    __tablename__ = "project_delivery_settings"
    __table_args__ = {
        "comment": "Per-project delivery analytics configuration: cycle time state mapping, backlog health thresholds, ready states, and t-shirt sizing field.",
    }

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        comment="Auto-generated unique identifier",
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        unique=True, nullable=False,
        comment="Project this configuration belongs to (one row per project)",
    )

    cycle_time_start_states: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False,
        default=lambda: list(DEFAULT_CYCLE_START_STATES),
        comment="Work item states that mark the START of cycle time (e.g. Active)",
    )
    cycle_time_end_states: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False,
        default=lambda: list(DEFAULT_CYCLE_END_STATES),
        comment="Work item states that mark the END of cycle time (e.g. Closed). Using Closed excludes PR review/testing time that ends at Resolved.",
    )
    review_states: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False,
        default=lambda: list(DEFAULT_REVIEW_STATES),
        comment="States representing the code review phase",
    )
    testing_states: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False,
        default=lambda: list(DEFAULT_TESTING_STATES),
        comment="States representing the testing/QA phase",
    )
    ready_states: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False,
        default=lambda: list(DEFAULT_READY_STATES),
        comment="Backlog states that count as 'ready to pick up' for planning-horizon calculations",
    )
    tshirt_custom_field: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Optional custom_fields key to treat as t-shirt size (e.g. 'Custom.TShirtSize')",
    )

    backlog_health_thresholds: Mapped[dict] = mapped_column(
        JSONB, nullable=False,
        default=lambda: dict(DEFAULT_HEALTH_THRESHOLDS),
        comment="Tunable thresholds for trusted-backlog pillar scoring",
    )

    long_running_threshold_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=14,
        comment="Active-to-now days above which a story is flagged as long-running",
    )

    rolling_capacity_sprints: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3,
        comment="Number of completed sprints to average for rolling capacity calculations",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        comment="Timestamp when the settings row was created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Timestamp of the last settings change",
    )

    project = relationship("Project")
