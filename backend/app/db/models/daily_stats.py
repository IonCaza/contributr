import uuid
from datetime import date

from sqlalchemy import Integer, Date, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DailyContributorStats(Base):
    __tablename__ = "daily_contributor_stats"
    __table_args__ = (
        UniqueConstraint("contributor_id", "repository_id", "date", name="uq_contributor_repo_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contributor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contributors.id", ondelete="CASCADE"), nullable=False, index=True)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    commits: Mapped[int] = mapped_column(Integer, default=0)
    lines_added: Mapped[int] = mapped_column(Integer, default=0)
    lines_deleted: Mapped[int] = mapped_column(Integer, default=0)
    files_changed: Mapped[int] = mapped_column(Integer, default=0)
    merges: Mapped[int] = mapped_column(Integer, default=0)
    prs_opened: Mapped[int] = mapped_column(Integer, default=0)
    prs_merged: Mapped[int] = mapped_column(Integer, default=0)
    reviews_given: Mapped[int] = mapped_column(Integer, default=0)
    pr_comments: Mapped[int] = mapped_column(Integer, default=0)
