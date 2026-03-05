import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.project import project_contributors


class Contributor(Base):
    __tablename__ = "contributors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    alias_emails: Mapped[list[str] | None] = mapped_column(ARRAY(String(320)), default=list)
    alias_names: Mapped[list[str] | None] = mapped_column(ARRAY(String(255)), default=list)
    github_username: Mapped[str | None] = mapped_column(String(255))
    gitlab_username: Mapped[str | None] = mapped_column(String(255))
    azure_username: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    commits = relationship("Commit", back_populates="contributor")
    pull_requests = relationship("PullRequest", back_populates="contributor")
    reviews = relationship("Review", back_populates="reviewer")
    projects = relationship("Project", secondary=project_contributors, back_populates="contributors")
    aliases = relationship("ContributorAlias", back_populates="contributor", cascade="all, delete-orphan")


class ContributorAlias(Base):
    __tablename__ = "contributor_aliases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contributor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contributors.id", ondelete="CASCADE"), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))

    contributor = relationship("Contributor", back_populates="aliases")
