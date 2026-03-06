import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Commit(Base):
    __tablename__ = "commits"
    __table_args__ = (
        UniqueConstraint("repository_id", "sha", name="uq_repo_sha"),
        {"comment": "Individual Git commit with authoring metadata, code churn statistics (lines added, deleted, files changed), and merge flag."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="Auto-generated unique identifier")
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True, comment="Repository this commit belongs to")
    contributor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contributors.id"), index=True, comment="Contributor who authored this commit")
    sha: Mapped[str] = mapped_column(String(40), nullable=False, index=True, comment="Full 40-character Git commit hash")
    message: Mapped[str | None] = mapped_column(String(4096), comment="Commit message text (truncated to 4096 chars)")
    branch: Mapped[str | None] = mapped_column(String(255), comment="Branch this commit was originally made on")
    is_merge: Mapped[bool] = mapped_column(Boolean, default=False, comment="Whether this is a merge commit combining two or more branches")
    lines_added: Mapped[int] = mapped_column(Integer, default=0, comment="Total lines added across all files in this commit")
    lines_deleted: Mapped[int] = mapped_column(Integer, default=0, comment="Total lines removed across all files in this commit")
    files_changed: Mapped[int] = mapped_column(Integer, default=0, comment="Number of files modified in this commit")
    authored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True, comment="Timestamp when the commit was originally authored")
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="Timestamp when the commit was applied (may differ from authored_at for rebases)")

    repository = relationship("Repository", back_populates="commits")
    contributor = relationship("Contributor", back_populates="commits")
    branches = relationship("Branch", secondary="commit_branches", back_populates="commits")
    files = relationship("CommitFile", back_populates="commit", cascade="all, delete-orphan")
