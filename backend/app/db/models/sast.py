import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SastScanStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SastSeverity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class SastConfidence(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SastFindingStatus(str, enum.Enum):
    OPEN = "open"
    FIXED = "fixed"
    DISMISSED = "dismissed"
    FALSE_POSITIVE = "false_positive"


class SastScanRun(Base):
    __tablename__ = "sast_scan_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[SastScanStatus] = mapped_column(
        SAEnum(SastScanStatus, values_callable=lambda e: [x.value for x in e], create_type=False),
        default=SastScanStatus.QUEUED,
        nullable=False,
    )
    branch: Mapped[str | None] = mapped_column(String(500))
    commit_sha: Mapped[str | None] = mapped_column(String(40))
    tool: Mapped[str] = mapped_column(String(50), default="semgrep")
    config_profile_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sast_rule_profiles.id", ondelete="SET NULL"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    findings_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    repository = relationship("Repository")
    project = relationship("Project")
    config_profile = relationship("SastRuleProfile")
    findings = relationship("SastFinding", back_populates="scan_run", cascade="all, delete-orphan")


class SastFinding(Base):
    __tablename__ = "sast_findings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sast_scan_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    rule_id: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    severity: Mapped[SastSeverity] = mapped_column(
        SAEnum(SastSeverity, values_callable=lambda e: [x.value for x in e], create_type=False),
        nullable=False,
    )
    confidence: Mapped[SastConfidence] = mapped_column(
        SAEnum(SastConfidence, values_callable=lambda e: [x.value for x in e], create_type=False),
        default=SastConfidence.MEDIUM,
    )
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    start_col: Mapped[int | None] = mapped_column(Integer)
    end_col: Mapped[int | None] = mapped_column(Integer)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    code_snippet: Mapped[str | None] = mapped_column(Text)
    fix_suggestion: Mapped[str | None] = mapped_column(Text)
    cwe_ids: Mapped[list | None] = mapped_column(JSONB, default=list)
    owasp_ids: Mapped[list | None] = mapped_column(JSONB, default=list)
    extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict)

    status: Mapped[SastFindingStatus] = mapped_column(
        SAEnum(SastFindingStatus, values_callable=lambda e: [x.value for x in e], create_type=False),
        default=SastFindingStatus.OPEN,
        nullable=False,
    )
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    scan_run = relationship("SastScanRun", back_populates="findings")
    repository = relationship("Repository")
    project = relationship("Project")
    dismissed_by = relationship("User")


class SastRuleProfile(Base):
    __tablename__ = "sast_rule_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    rulesets: Mapped[list] = mapped_column(JSONB, default=lambda: ["auto"])
    custom_rules_yaml: Mapped[str | None] = mapped_column(Text)
    scan_branches: Mapped[list] = mapped_column(JSONB, default=list)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class SastIgnoredRule(Base):
    __tablename__ = "sast_ignored_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_id: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    repository_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    repository = relationship("Repository")
    created_by = relationship("User")
