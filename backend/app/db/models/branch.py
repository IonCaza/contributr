import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, ForeignKey, UniqueConstraint, Table, Column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


commit_branches = Table(
    "commit_branches",
    Base.metadata,
    Column("commit_id", UUID(as_uuid=True), ForeignKey("commits.id", ondelete="CASCADE"), primary_key=True, comment="Commit in the association"),
    Column("branch_id", UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), primary_key=True, comment="Branch in the association"),
    comment="Association table linking commits to branches they appear on.",
)


class Branch(Base):
    __tablename__ = "branches"
    __table_args__ = (
        UniqueConstraint("repository_id", "name", name="uq_repo_branch_name"),
        {"comment": "Git branch within a repository, linked to commits via the commit_branches association."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="Auto-generated unique identifier")
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True, comment="Repository this branch belongs to")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="Full branch name (e.g. main, feature/auth)")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, comment="Whether this is the repository's default branch")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment="Timestamp when the branch was first detected")

    repository = relationship("Repository", back_populates="branches")
    commits = relationship("Commit", secondary=commit_branches, back_populates="branches")
