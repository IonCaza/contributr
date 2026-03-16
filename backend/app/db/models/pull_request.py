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
    __table_args__ = {
        "comment": "Pull/merge request with lifecycle timestamps, review metrics (iteration count, comment count), and current state (open/merged/closed).",
    }

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="Auto-generated unique identifier")
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True, comment="Repository this pull request targets")
    contributor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contributors.id"), index=True, comment="Contributor who opened the pull request")
    platform_pr_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="Numeric PR/MR identifier on the hosting platform")
    title: Mapped[str | None] = mapped_column(String(1024), comment="Pull request title/subject line")
    state: Mapped[PRState] = mapped_column(SAEnum(PRState), nullable=False, comment="Current lifecycle state: open, merged, or closed")
    lines_added: Mapped[int] = mapped_column(Integer, default=0, comment="Total lines added across all commits in the PR")
    lines_deleted: Mapped[int] = mapped_column(Integer, default=0, comment="Total lines removed across all commits in the PR")
    comment_count: Mapped[int] = mapped_column(SmallInteger, default=0, comment="Total number of review comments on the PR")
    iteration_count: Mapped[int] = mapped_column(SmallInteger, default=0, comment="Number of review rounds/iterations before merge")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="Timestamp when the PR was opened")
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="Timestamp when the PR was merged (null if not merged)")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="Timestamp when the PR was closed without merging (null if open or merged)")
    first_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="Timestamp of the first review submitted on the PR")

    repository = relationship("Repository", back_populates="pull_requests")
    contributor = relationship("Contributor", back_populates="pull_requests")
    reviews = relationship("Review", back_populates="pull_request", cascade="all, delete-orphan")
    comments = relationship("PRComment", back_populates="pull_request", cascade="all, delete-orphan")
