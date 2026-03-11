import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DepScanStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class DepFindingSeverity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class DepFindingStatus(str, enum.Enum):
    ACTIVE = "active"
    FIXED = "fixed"
    DISMISSED = "dismissed"


class DepScanRun(Base):
    __tablename__ = "dep_scan_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[DepScanStatus] = mapped_column(
        SAEnum(DepScanStatus, values_callable=lambda e: [x.value for x in e], create_type=False),
        default=DepScanStatus.QUEUED,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    findings_count: Mapped[int] = mapped_column(Integer, default=0)
    vulnerable_count: Mapped[int] = mapped_column(Integer, default=0)
    outdated_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    repository = relationship("Repository")
    project = relationship("Project")
    findings = relationship("DependencyFinding", back_populates="scan_run", cascade="all, delete-orphan")


class DependencyFinding(Base):
    __tablename__ = "dependency_findings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dep_scan_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    file_path: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    file_type: Mapped[str] = mapped_column(String(100), nullable=False)
    ecosystem: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    package_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    current_version: Mapped[str | None] = mapped_column(String(200))
    latest_version: Mapped[str | None] = mapped_column(String(200))

    is_outdated: Mapped[bool] = mapped_column(Boolean, default=False)
    is_vulnerable: Mapped[bool] = mapped_column(Boolean, default=False)
    is_direct: Mapped[bool] = mapped_column(Boolean, default=True)

    severity: Mapped[DepFindingSeverity] = mapped_column(
        SAEnum(DepFindingSeverity, values_callable=lambda e: [x.value for x in e], create_type=False),
        default=DepFindingSeverity.NONE,
        nullable=False,
    )
    vulnerabilities: Mapped[list | None] = mapped_column(JSONB, default=list)
    dep_license: Mapped[str | None] = mapped_column("license", String(200))

    status: Mapped[DepFindingStatus] = mapped_column(
        SAEnum(DepFindingStatus, values_callable=lambda e: [x.value for x in e], create_type=False),
        default=DepFindingStatus.ACTIVE,
        nullable=False,
    )
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    scan_run = relationship("DepScanRun", back_populates="findings")
    repository = relationship("Repository")
    project = relationship("Project")
    dismissed_by = relationship("User")
