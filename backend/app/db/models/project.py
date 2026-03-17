import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Table, Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

project_contributors = Table(
    "project_contributors",
    Base.metadata,
    Column("project_id", UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True, comment="Parent project"),
    Column("contributor_id", UUID(as_uuid=True), ForeignKey("contributors.id", ondelete="CASCADE"), primary_key=True, comment="Associated contributor"),
    comment="Association table linking projects to their contributors.",
)


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = {
        "comment": "Top-level grouping that organizes repositories and contributors. Each project tracks code contributions across one or more repositories.",
    }

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="Auto-generated unique identifier")
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, comment="Human-readable project name, must be unique")
    description: Mapped[str | None] = mapped_column(Text, comment="Optional free-text project description")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment="Timestamp when the project was created")
    platform_credential_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("platform_credentials.id", ondelete="SET NULL"),
        comment="API credential used for syncing repositories in this project",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Timestamp of the last modification",
    )

    repositories = relationship("Repository", back_populates="project", cascade="all, delete-orphan")
    contributors = relationship("Contributor", secondary=project_contributors, back_populates="projects")
    platform_credential = relationship("PlatformCredential")
    delivery_sync_jobs = relationship("DeliverySyncJob", back_populates="project", cascade="all, delete-orphan", order_by="DeliverySyncJob.created_at.desc()")
    schedule = relationship("ProjectSchedule", back_populates="project", uselist=False, cascade="all, delete-orphan")
