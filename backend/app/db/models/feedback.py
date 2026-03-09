import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FeedbackSource(str, enum.Enum):
    AGENT = "agent"
    HUMAN = "human"


class FeedbackStatus(str, enum.Enum):
    NEW = "new"
    REVIEWED = "reviewed"
    RESOLVED = "resolved"


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = {
        "comment": (
            "Stores both agent-reported capability gaps and human-submitted feedback. "
            "Agent entries are created automatically when an agent calls report_capability_gap; "
            "human entries come from thumbs-down reactions or manual submissions."
        ),
    }

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        comment="Auto-generated unique identifier",
    )
    source: Mapped[str] = mapped_column(
        String(10), nullable=False,
        comment="Origin of the feedback: agent (auto-reported capability gap) or human (manual submission)",
    )
    category: Mapped[str | None] = mapped_column(
        String(100),
        comment="Classification: capability_gap, missing_data, missing_tool, integration_needed, bug, suggestion, other",
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="Description of the gap or feedback",
    )
    user_query: Mapped[str | None] = mapped_column(
        Text,
        comment="The user's original question that triggered the gap report (agent source only)",
    )
    agent_slug: Mapped[str | None] = mapped_column(
        String(100),
        comment="Slug of the agent that reported the gap (null for human feedback)",
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="SET NULL"),
        index=True,
        comment="Chat session where the feedback originated",
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        comment="User who submitted the feedback (null for agent-sourced without session context)",
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_messages.id", ondelete="SET NULL"),
        comment="Specific chat message the feedback is about (thumbs-down on a message)",
    )
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, default=FeedbackStatus.NEW.value,
        comment="Review status: new, reviewed, or resolved",
    )
    admin_notes: Mapped[str | None] = mapped_column(
        Text,
        comment="Notes added by an admin when reviewing the feedback",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        comment="Timestamp when the feedback was created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Timestamp of the last modification",
    )

    session = relationship("ChatSession")
    user = relationship("User")
    message = relationship("ChatMessage")
