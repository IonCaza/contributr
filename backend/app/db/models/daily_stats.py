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
        {"comment": "Pre-aggregated daily metrics per contributor per repository, including commits, lines changed, PRs, reviews, and comments."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="Auto-generated unique identifier")
    contributor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contributors.id", ondelete="CASCADE"), nullable=False, index=True, comment="Contributor these daily stats belong to")
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True, comment="Repository these daily stats are scoped to")
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True, comment="Calendar date for the aggregated metrics")
    commits: Mapped[int] = mapped_column(Integer, default=0, comment="Number of commits on this date")
    lines_added: Mapped[int] = mapped_column(Integer, default=0, comment="Total lines added on this date")
    lines_deleted: Mapped[int] = mapped_column(Integer, default=0, comment="Total lines removed on this date")
    files_changed: Mapped[int] = mapped_column(Integer, default=0, comment="Number of distinct files modified on this date")
    merges: Mapped[int] = mapped_column(Integer, default=0, comment="Number of merge commits on this date")
    prs_opened: Mapped[int] = mapped_column(Integer, default=0, comment="Number of pull requests opened on this date")
    prs_merged: Mapped[int] = mapped_column(Integer, default=0, comment="Number of pull requests merged on this date")
    reviews_given: Mapped[int] = mapped_column(Integer, default=0, comment="Number of code reviews submitted on this date")
    pr_comments: Mapped[int] = mapped_column(Integer, default=0, comment="Number of PR review comments made on this date")
