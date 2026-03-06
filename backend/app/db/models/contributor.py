import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.project import project_contributors


class Contributor(Base):
    __tablename__ = "contributors"
    __table_args__ = {
        "comment": "Unified contributor identity that aggregates commits, pull requests, and reviews across repositories. Supports multiple email aliases and platform usernames.",
    }

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="Auto-generated unique identifier")
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="Primary display name for the contributor")
    canonical_email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True, comment="Primary email address, used as the unique identity key")
    alias_emails: Mapped[list[str] | None] = mapped_column(ARRAY(String(320)), default=list, comment="Additional email addresses associated with this contributor")
    alias_names: Mapped[list[str] | None] = mapped_column(ARRAY(String(255)), default=list, comment="Additional names associated with this contributor")
    github_username: Mapped[str | None] = mapped_column(String(255), comment="GitHub platform username")
    gitlab_username: Mapped[str | None] = mapped_column(String(255), comment="GitLab platform username")
    azure_username: Mapped[str | None] = mapped_column(String(255), comment="Azure DevOps platform username")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment="Timestamp when the contributor was first detected")

    commits = relationship("Commit", back_populates="contributor")
    pull_requests = relationship("PullRequest", back_populates="contributor")
    reviews = relationship("Review", back_populates="reviewer")
    projects = relationship("Project", secondary=project_contributors, back_populates="contributors")
    aliases = relationship("ContributorAlias", back_populates="contributor", cascade="all, delete-orphan")


class ContributorAlias(Base):
    __tablename__ = "contributor_aliases"
    __table_args__ = {
        "comment": "Alternate email or name mapping to a canonical contributor, used to merge contributions from the same person using different Git identities.",
    }

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="Auto-generated unique identifier")
    contributor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contributors.id", ondelete="CASCADE"), nullable=False, comment="Canonical contributor this alias belongs to")
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False, comment="Alternate email address that maps to the canonical contributor")
    name: Mapped[str | None] = mapped_column(String(255), comment="Alternate name associated with this email alias")

    contributor = relationship("Contributor", back_populates="aliases")
