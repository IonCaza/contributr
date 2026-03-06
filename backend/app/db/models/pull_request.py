import uuid
from datetime import datetime, timezone
import enum

from sqlalchemy import String, Integer, DateTime, ForeignKey, Enum as SAEnum, SmallInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PRState(str, enum.Enum):
    OPEN = "open"
    MERGED = "merged"
    CLOSED = "closed"


class PullRequest(Base):
    __tablename__ = "pull_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    contributor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contributors.id"), index=True)
    platform_pr_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(1024))
    state: Mapped[PRState] = mapped_column(SAEnum(PRState), nullable=False)
    lines_added: Mapped[int] = mapped_column(Integer, default=0)
    lines_deleted: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(SmallInteger, default=0)
    iteration_count: Mapped[int] = mapped_column(SmallInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    repository = relationship("Repository", back_populates="pull_requests")
    contributor = relationship("Contributor", back_populates="pull_requests")
    reviews = relationship("Review", back_populates="pull_request", cascade="all, delete-orphan")
