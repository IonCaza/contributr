import uuid
from datetime import date, datetime, timezone

from sqlalchemy import String, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Iteration(Base):
    __tablename__ = "iterations"
    __table_args__ = (
        UniqueConstraint("project_id", "path", name="uq_iteration_project_path"),
        {"comment": "Sprint or iteration period within a project. Imported from Azure DevOps or created manually for velocity tracking."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="Auto-generated unique identifier")
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="Project this iteration belongs to")
    platform_iteration_id: Mapped[str | None] = mapped_column(String(255), comment="External iteration identifier on the source platform for dedup")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="Display name of the iteration (e.g. Sprint 1)")
    path: Mapped[str | None] = mapped_column(String(1024), comment="Full iteration path (e.g. MyProject\\Sprint 1)")
    start_date: Mapped[date | None] = mapped_column(Date, comment="Planned start date of the iteration")
    end_date: Mapped[date | None] = mapped_column(Date, comment="Planned end date of the iteration")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment="Timestamp when the iteration was created")

    project = relationship("Project")
