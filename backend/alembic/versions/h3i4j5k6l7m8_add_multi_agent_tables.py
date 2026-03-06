"""add multi-agent tables (llm_providers, agents, agent_tool_assignments)

Revision ID: h3i4j5k6l7m8
Revises: g2h3i4j5k6l7
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "h3i4j5k6l7m8"
down_revision = "g2h3i4j5k6l7"
branch_labels = None
depends_on = None

CONTRIBUTION_ANALYST_ID = "00000000-0000-0000-0000-000000000010"
DEFAULT_PROVIDER_ID = "00000000-0000-0000-0000-000000000020"
SINGLETON_AI_SETTINGS_ID = "00000000-0000-0000-0000-000000000001"

TOOL_SLUGS = [
    "find_project",
    "find_contributor",
    "find_repository",
    "get_project_overview",
    "get_top_contributors",
    "get_contributor_profile",
    "get_repository_overview",
    "get_pr_activity",
    "get_contribution_trends",
    "get_code_hotspots",
]


def upgrade():
    op.create_table(
        "llm_providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("provider_type", sa.String(100), nullable=False, server_default="openai"),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("api_key_encrypted", sa.String(2048), nullable=True),
        sa.Column("base_url", sa.String(2048), nullable=True),
        sa.Column("temperature", sa.Float, nullable=False, server_default="0.1"),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "llm_provider_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("llm_providers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("system_prompt", sa.Text, nullable=False, server_default=""),
        sa.Column("max_iterations", sa.Integer, nullable=False, server_default="10"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("is_builtin", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "agent_tool_assignments",
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("tool_slug", sa.String(100), primary_key=True),
    )

    op.add_column(
        "chat_sessions",
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # --- Data migration: move existing AiSettings row into LlmProvider + Agent ---
    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT model, api_key_encrypted, base_url, temperature, max_iterations "
                "FROM ai_settings WHERE id = :id"),
        {"id": SINGLETON_AI_SETTINGS_ID},
    ).fetchone()

    if row and row[0]:
        model_name = row[0]
        provider_type = "openai"
        if "/" in model_name:
            provider_type = model_name.split("/")[0]

        conn.execute(
            sa.text(
                "INSERT INTO llm_providers (id, name, provider_type, model, api_key_encrypted, "
                "base_url, temperature, is_default) "
                "VALUES (:id, :name, :ptype, :model, :key, :url, :temp, true)"
            ),
            {
                "id": DEFAULT_PROVIDER_ID,
                "name": f"Default ({model_name})",
                "ptype": provider_type,
                "model": model_name,
                "key": row[1],
                "url": row[2],
                "temp": row[3],
            },
        )

        max_iter = row[4] or 10
        conn.execute(
            sa.text(
                "INSERT INTO agents (id, slug, name, description, llm_provider_id, "
                "system_prompt, max_iterations, enabled, is_builtin) "
                "VALUES (:id, :slug, :name, :desc, :llm, :prompt, :mi, true, true)"
            ),
            {
                "id": CONTRIBUTION_ANALYST_ID,
                "slug": "contribution-analyst",
                "name": "Contribution Analyst",
                "desc": "Analyzes git contribution data across projects, repositories, and contributors.",
                "llm": DEFAULT_PROVIDER_ID,
                "prompt": "",
                "mi": max_iter,
            },
        )

        for slug in TOOL_SLUGS:
            conn.execute(
                sa.text(
                    "INSERT INTO agent_tool_assignments (agent_id, tool_slug) VALUES (:aid, :slug)"
                ),
                {"aid": CONTRIBUTION_ANALYST_ID, "slug": slug},
            )

    # Drop migrated columns from ai_settings (keep id, enabled, updated_at)
    op.drop_column("ai_settings", "model")
    op.drop_column("ai_settings", "api_key_encrypted")
    op.drop_column("ai_settings", "base_url")
    op.drop_column("ai_settings", "temperature")
    op.drop_column("ai_settings", "max_iterations")


def downgrade():
    op.add_column("ai_settings", sa.Column("model", sa.String(255), nullable=False, server_default="gpt-4o-mini"))
    op.add_column("ai_settings", sa.Column("api_key_encrypted", sa.String(2048), nullable=True))
    op.add_column("ai_settings", sa.Column("base_url", sa.String(2048), nullable=True))
    op.add_column("ai_settings", sa.Column("temperature", sa.Float, nullable=False, server_default="0.1"))
    op.add_column("ai_settings", sa.Column("max_iterations", sa.Integer, nullable=False, server_default="10"))

    op.drop_column("chat_sessions", "agent_id")
    op.drop_table("agent_tool_assignments")
    op.drop_table("agents")
    op.drop_table("llm_providers")
