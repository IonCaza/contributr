import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AgentActivity(Base):
    __tablename__ = "agent_activities"
    __table_args__ = (
        Index("ix_agent_activities_session_trigger", "session_id", "trigger_message_id"),
        {
            "comment": (
                "Records a child-agent delegation that occurred during a supervisor "
                "response, linking the triggering user message to the agent's output."
            ),
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trigger_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    response_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_slug: Mapped[str] = mapped_column(
        String(120), nullable=False,
        comment="Slug of the child agent that was delegated to",
    )
    run_id: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="LangGraph run_id for event correlation",
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, default="",
        comment="Accumulated text output from the child agent",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
    )

    session = relationship("ChatSession")
    trigger_message = relationship("ChatMessage", foreign_keys=[trigger_message_id])
    response_message = relationship("ChatMessage", foreign_keys=[response_message_id])
