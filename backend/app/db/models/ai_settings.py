import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SINGLETON_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class AiSettings(Base):
    """Single-row global toggle for the AI subsystem."""
    __tablename__ = "ai_settings"
    __table_args__ = {
        "comment": "Single-row global toggle controlling whether AI features are enabled.",
    }

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=SINGLETON_ID, comment="Fixed singleton row identifier")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="Master toggle for all AI features")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Timestamp of the last settings change",
    )
