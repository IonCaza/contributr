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
    __table_args__ = {
        "comment": "Git repository registered for contribution tracking. Stores clone URLs, platform type (GitHub/GitLab/Azure DevOps), and sync metadata.",
    }

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="Auto-generated unique identifier")
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, comment="Parent project this repository belongs to")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="Repository name as it appears on the hosting platform")
    clone_url: Mapped[str | None] = mapped_column(String(2048), comment="HTTPS clone URL")
    ssh_url: Mapped[str | None] = mapped_column(String(2048), comment="SSH clone URL")
    platform: Mapped[Platform] = mapped_column(SAEnum(Platform), nullable=False, comment="Source code hosting platform (github, gitlab, azure)")
    platform_owner: Mapped[str | None] = mapped_column(String(255), comment="Organization or user that owns the repo on the platform")
    platform_repo: Mapped[str | None] = mapped_column(String(255), comment="Repository name on the platform (may differ from display name)")
    default_branch: Mapped[str] = mapped_column(String(255), default="main", comment="Name of the default/main branch (e.g. main, master)")
    ssh_credential_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ssh_credentials.id"), comment="SSH key used for cloning, if applicable")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="Timestamp of the most recent successful data sync")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment="Timestamp when the repository was registered")

    project = relationship("Project", back_populates="repositories")
    ssh_credential = relationship("SSHCredential")
    commits = relationship("Commit", back_populates="repository", cascade="all, delete-orphan")
    pull_requests = relationship("PullRequest", back_populates="repository", cascade="all, delete-orphan")
    sync_jobs = relationship("SyncJob", back_populates="repository", cascade="all, delete-orphan")
    branches = relationship("Branch", back_populates="repository", cascade="all, delete-orphan")
