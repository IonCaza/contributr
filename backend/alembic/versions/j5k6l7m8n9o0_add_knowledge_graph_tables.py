"""add knowledge_graphs and agent_knowledge_graph_assignments tables

Revision ID: j5k6l7m8n9o0
Revises: i4j5k6l7m8n9
Create Date: 2026-03-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "j5k6l7m8n9o0"
down_revision = "i4j5k6l7m8n9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_graphs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("generation_mode", sa.String(50), nullable=False, server_default="schema_and_entities"),
        sa.Column("content", sa.Text, nullable=False, server_default=""),
        sa.Column("graph_data", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("excluded_entities", postgresql.ARRAY(sa.String(255)), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "agent_knowledge_graph_assignments",
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("knowledge_graph_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_graphs.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("agent_knowledge_graph_assignments")
    op.drop_table("knowledge_graphs")
