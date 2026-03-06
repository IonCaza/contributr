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
    __table_args__ = {
        "comment": "Code review submitted on a pull request. Tracks reviewer identity, review verdict (approved/changes_requested/commented), and timing.",
    }

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="Auto-generated unique identifier")
    pull_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False, index=True, comment="Pull request this review was submitted on")
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contributors.id"), index=True, comment="Contributor who submitted the review")
    state: Mapped[ReviewState] = mapped_column(SAEnum(ReviewState), nullable=False, comment="Review verdict: approved, changes_requested, or commented")
    comment_count: Mapped[int] = mapped_column(SmallInteger, default=0, comment="Number of inline comments in this review")
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="Timestamp when the review was submitted")

    pull_request = relationship("PullRequest", back_populates="reviews")
    reviewer = relationship("Contributor", back_populates="reviews")
