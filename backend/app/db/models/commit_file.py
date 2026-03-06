import uuid

from sqlalchemy import String, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CommitFile(Base):
    __tablename__ = "commit_files"
    __table_args__ = (
        UniqueConstraint("commit_id", "file_path", name="uq_commit_file"),
        {"comment": "Per-file change record within a commit. Tracks the file path and line-level additions and deletions."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="Auto-generated unique identifier")
    commit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("commits.id", ondelete="CASCADE"), nullable=False, index=True, comment="Parent commit this file change belongs to")
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False, index=True, comment="Full path of the changed file relative to repository root")
    lines_added: Mapped[int] = mapped_column(Integer, default=0, comment="Lines added in this specific file")
    lines_deleted: Mapped[int] = mapped_column(Integer, default=0, comment="Lines removed in this specific file")

    commit = relationship("Commit", back_populates="files")
