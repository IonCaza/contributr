import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.repository import Platform


class PlatformCredential(Base):
    __tablename__ = "platform_credentials"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[Platform] = mapped_column(SAEnum(Platform, create_constraint=False, native_enum=False), nullable=False)
    token_encrypted: Mapped[str] = mapped_column(String(4096), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(2048))
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    created_by_user = relationship("User")
