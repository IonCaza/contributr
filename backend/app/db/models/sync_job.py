import uuid
from datetime import datetime, timezone
import enum

from sqlalchemy import String, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SyncStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SyncJob(Base):
    __tablename__ = "sync_jobs"
    __table_args__ = {
        "comment": "Background repository sync task. Records status (queued/running/completed/failed), timing, and error details.",
    }

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="Auto-generated unique identifier")
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True, comment="Repository being synced")
    celery_task_id: Mapped[str | None] = mapped_column(String(255), comment="Celery background task identifier for tracking")
    status: Mapped[SyncStatus] = mapped_column(SAEnum(SyncStatus, values_callable=lambda e: [x.value for x in e]), default=SyncStatus.QUEUED, nullable=False, comment="Current sync state: queued, running, completed, failed, or cancelled")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="Timestamp when the sync started executing")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="Timestamp when the sync completed or failed")
    error_message: Mapped[str | None] = mapped_column(Text, comment="Error details if the sync failed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment="Timestamp when the sync job was queued")

    repository = relationship("Repository", back_populates="sync_jobs")
