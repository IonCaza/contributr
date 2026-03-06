import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    __table_args__ = {
        "comment": "User conversation thread with an AI agent, including running context summary for token management.",
    }

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="Auto-generated unique identifier")
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="User who owns this conversation")
    agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL"), comment="Agent assigned to this conversation")
    title: Mapped[str] = mapped_column(String(255), default="New chat", comment="Conversation title shown in the sidebar")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment="Timestamp when the conversation started")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Timestamp of the latest activity",
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None, comment="Timestamp when the conversation was archived (null = active)")
    context_summary: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Rolling structured summary of earlier messages for token management")

    user = relationship("User")
    agent = relationship("AgentConfig")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = {
        "comment": "Individual message in a chat session with role (user/assistant/tool) and content.",
    }

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="Auto-generated unique identifier")
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True, comment="Conversation this message belongs to")
    role: Mapped[MessageRole] = mapped_column(
        SAEnum(MessageRole, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
        comment="Message author role: user, assistant, or tool",
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="Full message text")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment="Timestamp when the message was sent")

    session = relationship("ChatSession", back_populates="messages")
