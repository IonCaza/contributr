import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SINGLETON_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class AiSettings(Base):
    """Single-row global settings for the AI subsystem."""
    __tablename__ = "ai_settings"
    __table_args__ = {
        "comment": "Single-row global settings controlling AI features, memory, and extraction.",
    }

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=SINGLETON_ID, comment="Fixed singleton row identifier")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="Master toggle for all AI features")

    # Long-term memory (vector store + tools)
    memory_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="Enable long-term vector memory, tools, and extraction")
    memory_embedding_provider_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("llm_providers.id", ondelete="SET NULL"),
        nullable=True,
        comment="Embedding provider for vector store (FK to llm_providers)",
    )

    # LangMem background extraction
    extraction_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="Enable background memory extraction via LangMem")
    extraction_provider_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("llm_providers.id", ondelete="SET NULL"),
        nullable=True,
        comment="Chat model used by LangMem extraction (FK to llm_providers)",
    )
    extraction_enable_inserts: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="LangMem: allow creating new memories")
    extraction_enable_updates: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="LangMem: allow updating existing memories")
    extraction_enable_deletes: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="LangMem: allow deleting contradicted memories")

    # Context management thresholds
    cleanup_threshold_ratio: Mapped[float] = mapped_column(Float, default=0.6, nullable=False, comment="Evict messages when checkpoint tokens exceed this fraction of context window")
    summary_token_ratio: Mapped[float] = mapped_column(Float, default=0.04, nullable=False, comment="Rolling summary size as a fraction of context window")

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Timestamp of the last settings change",
    )
