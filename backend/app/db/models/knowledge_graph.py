import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class KnowledgeGraph(Base):
    __tablename__ = "knowledge_graphs"
    __table_args__ = {
        "comment": "Knowledge graph storing structured data model context (schema, entities, relationships) for AI agent prompt injection.",
    }

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="Auto-generated unique identifier")
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, comment="Display name for the knowledge graph")
    description: Mapped[str | None] = mapped_column(Text, comment="Optional explanation of what the knowledge graph covers")
    generation_mode: Mapped[str] = mapped_column(String(50), nullable=False, default="schema_and_entities", comment="How the graph was generated: schema_only, entities_only, schema_and_entities, or manual")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="Markdown text injected into agent system prompts as data context")
    graph_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, comment="JSONB with nodes (entities) and edges (relationships) for visualization")
    excluded_entities: Mapped[list[str]] = mapped_column(ARRAY(String(255)), default=list, comment="Table names excluded from the graph")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        comment="Timestamp when the knowledge graph was created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Timestamp of the last modification",
    )


class AgentKnowledgeGraphAssignment(Base):
    __tablename__ = "agent_knowledge_graph_assignments"
    __table_args__ = {
        "comment": "Join table linking agents to knowledge graphs they use as context.",
    }

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Agent this knowledge graph is assigned to",
    )
    knowledge_graph_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_graphs.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Knowledge graph providing context to the agent",
    )

    knowledge_graph = relationship("KnowledgeGraph")
