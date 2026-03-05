import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db.base import Base


class Platform(str, enum.Enum):
    GITHUB = "github"
    GITLAB = "gitlab"
    AZURE = "azure"


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    clone_url: Mapped[str | None] = mapped_column(String(2048))
    ssh_url: Mapped[str | None] = mapped_column(String(2048))
    platform: Mapped[Platform] = mapped_column(SAEnum(Platform), nullable=False)
    platform_owner: Mapped[str | None] = mapped_column(String(255))
    platform_repo: Mapped[str | None] = mapped_column(String(255))
    default_branch: Mapped[str] = mapped_column(String(255), default="main")
    ssh_credential_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ssh_credentials.id"))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="repositories")
    ssh_credential = relationship("SSHCredential")
    commits = relationship("Commit", back_populates="repository", cascade="all, delete-orphan")
    pull_requests = relationship("PullRequest", back_populates="repository", cascade="all, delete-orphan")
    sync_jobs = relationship("SyncJob", back_populates="repository", cascade="all, delete-orphan")
    branches = relationship("Branch", back_populates="repository", cascade="all, delete-orphan")
