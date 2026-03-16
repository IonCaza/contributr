"""add adr tables and seed default templates

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None

NYGARD_TEMPLATE = """# {{number}}. {{title}}

Date: {{date}}

## Status

{{status}}

## Context

{{context}}

## Decision

{{decision}}

## Consequences

{{consequences}}
"""

MADR_TEMPLATE = """# {{number}}. {{title}}

- Status: {{status}}
- Deciders: {{deciders}}
- Date: {{date}}

## Context and Problem Statement

{{context}}

## Decision Drivers

{{drivers}}

## Considered Options

{{options}}

## Decision Outcome

{{decision}}

### Positive Consequences

{{pros}}

### Negative Consequences

{{cons}}
"""

LIGHTWEIGHT_TEMPLATE = """# ADR-{{number}}: {{title}}

**Status:** {{status}} | **Date:** {{date}}

## What
{{what}}

## Why
{{why}}

## How
{{how}}

## Impact
{{impact}}
"""


def upgrade() -> None:
    op.create_table(
        "adr_repositories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("repository_id", UUID(as_uuid=True), sa.ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("directory_path", sa.String(1024), nullable=False, server_default="docs/adr"),
        sa.Column("naming_convention", sa.String(255), nullable=False, server_default="{number:04d}-{slug}.md"),
        sa.Column("next_number", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_adr_repositories_project_id", "adr_repositories", ["project_id"])

    op.create_table(
        "adr_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1024), nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute(f"""
        INSERT INTO adr_templates (name, description, content, is_default)
        VALUES
            ('Nygard Classic', 'Michael Nygard''s original ADR format: Context, Decision, Consequences', $tmpl${NYGARD_TEMPLATE}$tmpl$, true),
            ('MADR', 'Markdown ADR: structured format with decision drivers, options, and outcome analysis', $tmpl${MADR_TEMPLATE}$tmpl$, false),
            ('Lightweight', 'Minimal ADR format: What, Why, How, Impact', $tmpl${LIGHTWEIGHT_TEMPLATE}$tmpl$, false)
    """)

    op.create_table(
        "adrs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("adr_number", sa.Integer, nullable=False),
        sa.Column("title", sa.String(1024), nullable=False),
        sa.Column("slug", sa.String(1024), nullable=False),
        sa.Column("status", sa.Enum("PROPOSED", "ACCEPTED", "DEPRECATED", "SUPERSEDED", "REJECTED", name="adrstatus"), nullable=False, server_default="PROPOSED"),
        sa.Column("content", sa.Text, nullable=False, server_default=""),
        sa.Column("template_id", UUID(as_uuid=True), sa.ForeignKey("adr_templates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("superseded_by_id", UUID(as_uuid=True), sa.ForeignKey("adrs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("file_path", sa.String(1024), nullable=True),
        sa.Column("last_committed_sha", sa.String(40), nullable=True),
        sa.Column("pr_url", sa.String(2048), nullable=True),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("adrs")
    op.execute("DROP TYPE IF EXISTS adrstatus")
    op.drop_table("adr_templates")
    op.drop_index("ix_adr_repositories_project_id", table_name="adr_repositories")
    op.drop_table("adr_repositories")
