import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ScheduleInterval(str, enum.Enum):
    DISABLED = "disabled"
    EVERY_HOUR = "every_hour"
    EVERY_6_HOURS = "every_6_hours"
    EVERY_12_HOURS = "every_12_hours"
    DAILY = "daily"
    EVERY_2_DAYS = "every_2_days"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class ProjectSchedule(Base):
    __tablename__ = "project_schedules"
    __table_args__ = {
        "comment": "Per-project scheduling configuration controlling how often automated tasks run.",
    }

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        comment="Auto-generated unique identifier",
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"),
        unique=True, nullable=False,
        comment="The project this schedule belongs to (one schedule per project)",
    )

    repo_sync_interval: Mapped[str] = mapped_column(
        String(32), default=ScheduleInterval.DISABLED.value, nullable=False,
        comment="How often to sync all repositories in this project",
    )
    repo_sync_last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="When repo sync was last dispatched by the scheduler",
    )

    delivery_sync_interval: Mapped[str] = mapped_column(
        String(32), default=ScheduleInterval.DISABLED.value, nullable=False,
        comment="How often to sync Azure DevOps work items and delivery data",
    )
    delivery_sync_last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="When delivery sync was last dispatched by the scheduler",
    )

    security_scan_interval: Mapped[str] = mapped_column(
        String(32), default=ScheduleInterval.DISABLED.value, nullable=False,
        comment="How often to run SAST security scans on all repositories",
    )
    security_scan_last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="When security scan was last dispatched by the scheduler",
    )

    dependency_scan_interval: Mapped[str] = mapped_column(
        String(32), default=ScheduleInterval.DISABLED.value, nullable=False,
        comment="How often to run dependency vulnerability scans on all repositories",
    )
    dependency_scan_last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="When dependency scan was last dispatched by the scheduler",
    )

    insights_interval: Mapped[str] = mapped_column(
        String(32), default=ScheduleInterval.DAILY.value, nullable=False,
        comment="How often to generate project insights analysis",
    )
    insights_last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="When insights generation was last dispatched by the scheduler",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        comment="Timestamp when the schedule was created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Timestamp of the last schedule modification",
    )

    project = relationship("Project", back_populates="schedule")
