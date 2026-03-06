import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AgentToolAssignment(Base):
    __tablename__ = "agent_tool_assignments"
    __table_args__ = {
        "comment": "Join table linking agents to their enabled tools.",
    }

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Agent this tool is assigned to",
    )
    tool_slug: Mapped[str] = mapped_column(String(100), primary_key=True, comment="Unique identifier of the assigned tool")


class AgentConfig(Base):
    __tablename__ = "agents"
    __table_args__ = {
        "comment": "AI agent definition with system prompt, assigned tools, LLM provider, and iteration limits.",
    }

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="Auto-generated unique identifier")
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, comment="URL-safe unique identifier (e.g. contribution-analyst)")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="Display name shown in the UI")
    description: Mapped[str | None] = mapped_column(Text, comment="Explains the agent's purpose and capabilities")
    llm_provider_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("llm_providers.id", ondelete="SET NULL"),
        comment="LLM provider used for inference",
    )
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="Instructions and context injected at the start of every conversation")
    max_iterations: Mapped[int] = mapped_column(Integer, default=10, nullable=False, comment="Maximum tool-calling rounds before the agent must respond")
    summary_token_limit: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Maximum tokens for conversation summary (null = auto-detect)")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="Whether the agent is available for use")
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="Whether this agent was auto-seeded and should not be deleted")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        comment="Timestamp when the agent was created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Timestamp of the last modification",
    )

    llm_provider = relationship("LlmProvider", back_populates="agents")
    tool_assignments = relationship(
        "AgentToolAssignment", cascade="all, delete-orphan", lazy="selectin"
    )
    knowledge_graph_assignments = relationship(
        "AgentKnowledgeGraphAssignment", cascade="all, delete-orphan", lazy="selectin"
    )
