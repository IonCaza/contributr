import uuid
from datetime import datetime
import enum

from sqlalchemy import DateTime, ForeignKey, Enum as SAEnum, SmallInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReviewState(str, enum.Enum):
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    COMMENTED = "commented"


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pull_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contributors.id"), index=True)
    state: Mapped[ReviewState] = mapped_column(SAEnum(ReviewState), nullable=False)
    comment_count: Mapped[int] = mapped_column(SmallInteger, default=0)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    pull_request = relationship("PullRequest", back_populates="reviews")
    reviewer = relationship("Contributor", back_populates="reviews")
