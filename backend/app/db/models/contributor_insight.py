import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ContributorInsightCategory(str, enum.Enum):
    HABITS = "habits"
    CODE_CRAFT = "code_craft"
    COLLABORATION = "collaboration"
    GROWTH = "growth"
    KNOWLEDGE = "knowledge"


class ContributorInsightRun(Base):
    __tablename__ = "contributor_insight_runs"
    __table_args__ = {
        "comment": "Record of each insights analysis run for a contributor.",
    }

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contributor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contributors.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    findings_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)

    contributor = relationship("Contributor")
    findings = relationship("ContributorInsightFinding", back_populates="run", cascade="all, delete-orphan")


class ContributorInsightFinding(Base):
    __tablename__ = "contributor_insight_findings"
    __table_args__ = {
        "comment": "Individual insight finding for a contributor, tracked by slug for deduplication.",
    }

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contributor_insight_runs.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    contributor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contributors.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    recommendation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metric_data: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    affected_entities: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    run = relationship("ContributorInsightRun", back_populates="findings")
    contributor = relationship("Contributor")
    dismissed_by = relationship("User")
