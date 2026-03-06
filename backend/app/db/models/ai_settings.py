import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Float, Integer, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SINGLETON_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class AiSettings(Base):
    """Single-row table holding AI agent configuration.

    The api_key_encrypted column is Fernet-encrypted using the app secret_key,
    matching the pattern used by SSHCredential.
    """
    __tablename__ = "ai_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=SINGLETON_ID)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    model: Mapped[str] = mapped_column(String(255), default="gpt-4o-mini", nullable=False)
    api_key_encrypted: Mapped[str | None] = mapped_column(String(2048))
    base_url: Mapped[str | None] = mapped_column(String(2048))
    temperature: Mapped[float] = mapped_column(Float, default=0.1, nullable=False)
    max_iterations: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
