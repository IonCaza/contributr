"""Mapping between application User accounts and VCS Contributor identities."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Boolean, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserContributorLink(Base):
    __tablename__ = "user_contributor_links"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    contributor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contributors.id", ondelete="CASCADE"),
        primary_key=True,
    )
    linked_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    link_method: Mapped[str] = mapped_column(
        String(30), nullable=False, default="email_match",
        comment="How the link was created: email_match, admin, self_claim, oidc",
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    user = relationship("User", foreign_keys=[user_id])
    contributor = relationship("Contributor", foreign_keys=[contributor_id])
    linked_by = relationship("User", foreign_keys=[linked_by_id])
