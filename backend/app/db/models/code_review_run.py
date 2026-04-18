"""Code review job tracking — records webhook-triggered or manual code review runs."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CodeReviewTrigger(str, enum.Enum):
    WEBHOOK = "webhook"
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class CodeReviewStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CodeReviewVerdict(str, enum.Enum):
    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    COMMENT = "comment"


class CodeReviewRun(Base):
    __tablename__ = "code_review_runs"
    __table_args__ = {
        "comment": "Tracks automated code review jobs triggered by webhooks or manual API calls.",
    }

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    pull_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="SET NULL"),
        nullable=True,
    )
    platform_pr_number: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="The PR/MR number on the external platform",
    )
    trigger: Mapped[CodeReviewTrigger] = mapped_column(
        SAEnum(CodeReviewTrigger, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    status: Mapped[CodeReviewStatus] = mapped_column(
        SAEnum(CodeReviewStatus, values_callable=lambda e: [x.value for x in e]),
        default=CodeReviewStatus.QUEUED, nullable=False,
    )
    celery_task_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
    )
    findings_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    verdict: Mapped[CodeReviewVerdict | None] = mapped_column(
        SAEnum(CodeReviewVerdict, values_callable=lambda e: [x.value for x in e]),
        nullable=True,
    )
    review_url: Mapped[str | None] = mapped_column(
        String(1000), nullable=True,
        comment="Link to the posted review on the platform",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
    )

    project = relationship("Project")
    repository = relationship("Repository")
    pull_request = relationship("PullRequest", foreign_keys=[pull_request_id])
