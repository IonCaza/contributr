import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Commit(Base):
    __tablename__ = "commits"
    __table_args__ = (UniqueConstraint("repository_id", "sha", name="uq_repo_sha"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    contributor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contributors.id"), index=True)
    sha: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    message: Mapped[str | None] = mapped_column(String(4096))
    branch: Mapped[str | None] = mapped_column(String(255))
    is_merge: Mapped[bool] = mapped_column(Boolean, default=False)
    lines_added: Mapped[int] = mapped_column(Integer, default=0)
    lines_deleted: Mapped[int] = mapped_column(Integer, default=0)
    files_changed: Mapped[int] = mapped_column(Integer, default=0)
    authored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    repository = relationship("Repository", back_populates="commits")
    contributor = relationship("Contributor", back_populates="commits")
    branches = relationship("Branch", secondary="commit_branches", back_populates="commits")
    files = relationship("CommitFile", back_populates="commit", cascade="all, delete-orphan")
