import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CustomFieldConfig(Base):
    __tablename__ = "custom_field_configs"
    __table_args__ = (
        UniqueConstraint("project_id", "field_reference_name", name="uq_custom_field_project_ref"),
        {
            "comment": "Per-project configuration of additional platform fields to import during work item sync. "
            "Each row maps an ADO field reference name to a display name and type, with an enabled toggle.",
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        comment="Auto-generated unique identifier",
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
        comment="Project this custom field configuration belongs to",
    )
    field_reference_name: Mapped[str] = mapped_column(
        String(500), nullable=False,
        comment="Platform field reference name (e.g. Custom.ActualEffort)",
    )
    display_name: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Human-readable field label shown in the UI",
    )
    field_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="string",
        comment="Data type reported by the platform: string, double, integer, dateTime, boolean, etc.",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
        comment="Whether this field is actively imported during sync",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        comment="Timestamp when this configuration was created",
    )

    project = relationship("Project")
