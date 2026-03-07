import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class InsightRunStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class InsightSeverity(str, enum.Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class InsightCategory(str, enum.Enum):
    PROCESS = "process"
    DELIVERY = "delivery"
    TEAM_BALANCE = "team_balance"
    CODE_QUALITY = "code_quality"
    INTERSECTION = "intersection"


class InsightStatus(str, enum.Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class InsightRun(Base):
    __tablename__ = "insight_runs"
    __table_args__ = {
        "comment": "Record of each insights analysis run for a project.",
    }

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[InsightRunStatus] = mapped_column(
        SAEnum(InsightRunStatus, values_callable=lambda e: [x.value for x in e], create_type=False),
        default=InsightRunStatus.RUNNING,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    findings_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)

    project = relationship("Project")
    findings = relationship("InsightFinding", back_populates="run", cascade="all, delete-orphan")


class InsightFinding(Base):
    __tablename__ = "insight_findings"
    __table_args__ = {
        "comment": "Individual insight finding detected during analysis, tracked by slug for deduplication.",
    }

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("insight_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[InsightCategory] = mapped_column(
        SAEnum(InsightCategory, values_callable=lambda e: [x.value for x in e], create_type=False),
        nullable=False,
    )
    severity: Mapped[InsightSeverity] = mapped_column(
        SAEnum(InsightSeverity, values_callable=lambda e: [x.value for x in e], create_type=False),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    recommendation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metric_data: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    affected_entities: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    status: Mapped[InsightStatus] = mapped_column(
        SAEnum(InsightStatus, values_callable=lambda e: [x.value for x in e], create_type=False),
        default=InsightStatus.ACTIVE,
        nullable=False,
    )
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    run = relationship("InsightRun", back_populates="findings")
    project = relationship("Project")
    dismissed_by = relationship("User")
