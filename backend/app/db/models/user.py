import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {
        "comment": "Application user account with authentication credentials and admin flag.",
    }

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="Auto-generated unique identifier")
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False, comment="User email address, used for login")
    username: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False, comment="Unique login username")
    hashed_password: Mapped[str] = mapped_column(String(128), nullable=False, comment="Bcrypt-hashed password (never exposed via API)")
    full_name: Mapped[str | None] = mapped_column(String(255), comment="Optional display name")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, comment="Whether the user has administrative privileges")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="Whether the account is enabled for login")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment="Timestamp when the account was created")

    ssh_credentials = relationship("SSHCredential", back_populates="created_by_user")
