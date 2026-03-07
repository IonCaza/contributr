import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WorkItemCommit(Base):
    __tablename__ = "work_item_commits"
    __table_args__ = (
        UniqueConstraint("work_item_id", "commit_id", name="uq_work_item_commit"),
        {
            "comment": (
                "Junction table linking work items to code commits. "
                "Captures three link types: message_ref (commit message references like #12345 or AB#12345), "
                "artifact_link (platform-managed links from Azure DevOps artifact relations), "
                "and manual (user-created links). "
                "Enables cross-domain analytics between delivery tracking and codebase analysis."
            )
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        comment="Auto-generated unique identifier",
    )
    work_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("work_items.id", ondelete="CASCADE"),
        nullable=False, index=True,
        comment="Work item that is linked to a commit (CASCADE on delete)",
    )
    commit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commits.id", ondelete="CASCADE"),
        nullable=False, index=True,
        comment="Commit that is linked to a work item (CASCADE on delete)",
    )
    link_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="How the link was established: message_ref (parsed from commit message), artifact_link (from platform relation data), or manual (user-created)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        comment="Timestamp when this link was discovered or created",
    )

    work_item = relationship("WorkItem", backref="commit_links")
    commit = relationship("Commit", backref="work_item_links")
