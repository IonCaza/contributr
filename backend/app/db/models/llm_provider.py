import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Float, Integer, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LlmProvider(Base):
    __tablename__ = "llm_providers"
    __table_args__ = {
        "comment": "LLM provider configuration including model name, API key, base URL, temperature, and optional context window.",
    }

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="Auto-generated unique identifier")
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, comment="Display name for the provider configuration")
    provider_type: Mapped[str] = mapped_column(String(100), nullable=False, default="openai", comment="LLM provider backend (e.g. openai, anthropic, azure)")
    model: Mapped[str] = mapped_column(String(255), nullable=False, comment="Model identifier (e.g. gpt-4o, claude-3-sonnet)")
    api_key_encrypted: Mapped[str | None] = mapped_column(String(2048), comment="Fernet-encrypted API key")
    base_url: Mapped[str | None] = mapped_column(String(2048), comment="Custom API endpoint for proxies or self-hosted models")
    temperature: Mapped[float] = mapped_column(Float, default=0.1, nullable=False, comment="Sampling temperature (0.0 = deterministic, 1.0 = creative)")
    context_window: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Maximum token capacity of the model (null = auto-detect via LiteLLM)")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="Fallback provider when an agent has none assigned")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        comment="Timestamp when the provider was configured",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Timestamp of the last modification",
    )

    agents = relationship("AgentConfig", back_populates="llm_provider")
