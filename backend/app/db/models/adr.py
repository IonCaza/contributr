import uuid
from datetime import datetime, timezone
import enum
import re

from sqlalchemy import String, Integer, Boolean, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AdrStatus(str, enum.Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class AdrRepository(Base):
    __tablename__ = "adr_repositories"
    __table_args__ = {
        "comment": "Links a project to a git repository for ADR storage, including directory and naming conventions.",
    }

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    repository_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="SET NULL"),
        nullable=True,
    )
    directory_path: Mapped[str] = mapped_column(String(1024), default="docs/adr", nullable=False)
    naming_convention: Mapped[str] = mapped_column(String(255), default="{number:04d}-{slug}.md", nullable=False)
    next_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project = relationship("Project")
    repository = relationship("Repository")


class AdrTemplate(Base):
    __tablename__ = "adr_templates"
    __table_args__ = {
        "comment": "Reusable ADR templates with markdown placeholders for title, status, context, etc.",
    }

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project = relationship("Project", foreign_keys=[project_id])


class Adr(Base):
    __tablename__ = "adrs"
    __table_args__ = {
        "comment": "Individual Architecture Decision Record with status tracking, repo file path, and PR workflow state.",
    }

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    adr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(1024), nullable=False)
    slug: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[AdrStatus] = mapped_column(
        SAEnum(AdrStatus), nullable=False, default=AdrStatus.PROPOSED,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("adr_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("adrs.id", ondelete="SET NULL"),
        nullable=True,
    )
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    last_committed_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    pr_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project = relationship("Project")
    template = relationship("AdrTemplate", foreign_keys=[template_id])
    superseded_by = relationship("Adr", remote_side=[id], foreign_keys=[superseded_by_id])
    created_by = relationship("User", foreign_keys=[created_by_id])

    @staticmethod
    def make_slug(title: str) -> str:
        slug = title.lower().strip()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        return slug.strip("-")[:200]
