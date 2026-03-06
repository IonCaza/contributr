import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_team_project_name"),
        {"comment": "Platform-agnostic team grouping contributors within a project. Can be imported from Azure DevOps, GitHub, or created manually."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="Auto-generated unique identifier")
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="Project this team belongs to")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="Display name of the team")
    description: Mapped[str | None] = mapped_column(Text, comment="Optional description of the team's purpose or scope")
    platform: Mapped[str | None] = mapped_column(String(50), comment="Source platform the team was imported from (azure, github, or null for manual)")
    platform_team_id: Mapped[str | None] = mapped_column(String(255), comment="External team identifier on the source platform, used for dedup on re-sync")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment="Timestamp when the team was created")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Timestamp of the last modification",
    )

    project = relationship("Project")
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")


class TeamMember(Base):
    __tablename__ = "team_members"
    __table_args__ = {
        "comment": "Join table linking contributors to teams with an optional role designation.",
    }

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"),
        primary_key=True, comment="Team this membership belongs to",
    )
    contributor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contributors.id", ondelete="CASCADE"),
        primary_key=True, comment="Contributor who is a member of the team",
    )
    role: Mapped[str] = mapped_column(String(50), default="member", nullable=False, comment="Role within the team: member, lead, or admin")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment="Timestamp when the member joined the team")

    team = relationship("Team", back_populates="members")
    contributor = relationship("Contributor")
