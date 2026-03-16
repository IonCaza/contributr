import uuid
from datetime import datetime, timezone
import enum

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PRCommentType(str, enum.Enum):
    INLINE = "inline"
    GENERAL = "general"
    SYSTEM = "system"


class PRComment(Base):
    __tablename__ = "pr_comments"
    __table_args__ = {
        "comment": "Persisted PR/MR comment fetched from the hosting platform. Supports threaded/inline comments with file and line references.",
    }

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pull_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    author_name: Mapped[str] = mapped_column(String(255), nullable=False)
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contributors.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parent_comment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pr_comments.id", ondelete="CASCADE"),
        nullable=True,
    )
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    line_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment_type: Mapped[PRCommentType] = mapped_column(
        SAEnum(PRCommentType), nullable=False, default=PRCommentType.GENERAL,
    )
    platform_comment_id: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    pull_request = relationship("PullRequest", back_populates="comments")
    author = relationship("Contributor", foreign_keys=[author_id])
    parent_comment = relationship("PRComment", remote_side=[id], foreign_keys=[parent_comment_id])
