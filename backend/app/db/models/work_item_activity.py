import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WorkItemActivity(Base):
    """Individual revision/update on a work item, imported from the source platform's audit trail.

    Uniqueness is enforced at the DB layer by the functional index
    ``uq_work_item_activity_revision_field`` on
    ``(work_item_id, revision_number, COALESCE(field_name, ''))`` so a single
    revision can contribute multiple rows — one per changed field.
    """
    __tablename__ = "work_item_activities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    work_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contributor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contributors.id"),
        index=True,
    )
    action: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="High-level action: created, state_changed, assigned, field_changed, commented",
    )
    field_name: Mapped[str | None] = mapped_column(
        String(255),
        comment="Platform field reference that was changed (e.g. System.State)",
    )
    old_value: Mapped[str | None] = mapped_column(
        Text, comment="Previous value (truncated to 2 KB)",
    )
    new_value: Mapped[str | None] = mapped_column(
        Text, comment="New value after the change (truncated to 2 KB)",
    )
    revision_number: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="Platform revision/version number for dedup across re-syncs",
    )
    activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
        comment="Timestamp of the activity on the source platform",
    )

    work_item = relationship("WorkItem")
    contributor = relationship("Contributor")
