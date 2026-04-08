"""Add RBAC models and RLS policies for text-to-SQL scoping.

Revision ID: r5s6t7u8v9w0
Revises: q4r5s6t7u8v9
Create Date: 2026-04-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "r5s6t7u8v9w0"
down_revision = "q4r5s6t7u8v9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. RBAC tables (AccessPolicy + ResourceGrant)
    # ------------------------------------------------------------------
    op.create_table(
        "access_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("data_scope", sa.String(16), nullable=False, server_default="all"),
        sa.Column("agent_tool_policies", postgresql.JSONB, nullable=True),
        sa.Column("sql_allowed_tables", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("scope", "scope_id", name="uq_access_policy_scope"),
    )
    op.create_index("ix_access_policies_scope", "access_policies", ["scope", "scope_id"])

    op.create_table(
        "resource_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("grantee_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission", sa.String(16), nullable=False, server_default="view"),
        sa.Column("granted_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("resource_type", "resource_id", "grantee_user_id", name="uq_resource_grant"),
    )
    op.create_index("ix_resource_grants_grantee", "resource_grants", ["grantee_user_id"])
    op.create_index("ix_resource_grants_resource", "resource_grants", ["resource_type", "resource_id"])

    # ------------------------------------------------------------------
    # 2. Access audit log
    # ------------------------------------------------------------------
    op.create_table(
        "access_audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("resource_id", sa.String(128), nullable=True),
        sa.Column("outcome", sa.String(16), nullable=False, server_default="allowed"),
        sa.Column("detail", postgresql.JSONB, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_access_audit_user", "access_audit_logs", ["user_id"])
    op.create_index("ix_access_audit_created", "access_audit_logs", ["created_at"])
    op.create_index("ix_access_audit_action", "access_audit_logs", ["action"])

    # ------------------------------------------------------------------
    # 3. Identity linking tables
    # ------------------------------------------------------------------
    op.create_table(
        "user_contributor_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contributor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contributors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("linked_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("link_method", sa.String(32), nullable=False, server_default="email_match"),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", "contributor_id", name="uq_user_contributor_link"),
    )

    op.create_table(
        "project_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="viewer"),
        sa.Column("invited_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", "project_id", name="uq_project_membership"),
    )

    # ------------------------------------------------------------------
    # 4. Row-Level Security on key tables consumed by text-to-SQL
    # ------------------------------------------------------------------
    rls_tables = [
        "commits",
        "pull_requests",
        "reviews",
        "daily_contributor_stats",
        "repositories",
        "work_items",
    ]

    for table in rls_tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    # Repos: visible if project_id is in user's accessible set
    op.execute("""
        CREATE POLICY rls_repo_access ON repositories
        USING (
            current_setting('app.data_scope', true) = 'all'
            OR project_id::text = ANY(string_to_array(current_setting('app.current_project_ids', true), ','))
        )
    """)

    # Commits: visible if the repository's project is accessible or contributor matches
    op.execute("""
        CREATE POLICY rls_commit_access ON commits
        USING (
            current_setting('app.data_scope', true) = 'all'
            OR repository_id IN (
                SELECT id FROM repositories
                WHERE project_id::text = ANY(string_to_array(current_setting('app.current_project_ids', true), ','))
            )
            OR contributor_id::text = ANY(string_to_array(current_setting('app.current_contributor_ids', true), ','))
        )
    """)

    # Pull requests: same logic as commits
    op.execute("""
        CREATE POLICY rls_pr_access ON pull_requests
        USING (
            current_setting('app.data_scope', true) = 'all'
            OR repository_id IN (
                SELECT id FROM repositories
                WHERE project_id::text = ANY(string_to_array(current_setting('app.current_project_ids', true), ','))
            )
            OR contributor_id::text = ANY(string_to_array(current_setting('app.current_contributor_ids', true), ','))
        )
    """)

    # Reviews: visible via the PR's repository
    op.execute("""
        CREATE POLICY rls_review_access ON reviews
        USING (
            current_setting('app.data_scope', true) = 'all'
            OR pull_request_id IN (
                SELECT id FROM pull_requests
                WHERE repository_id IN (
                    SELECT id FROM repositories
                    WHERE project_id::text = ANY(string_to_array(current_setting('app.current_project_ids', true), ','))
                )
            )
            OR reviewer_id::text = ANY(string_to_array(current_setting('app.current_contributor_ids', true), ','))
        )
    """)

    # Daily stats: accessible via repository project or contributor
    op.execute("""
        CREATE POLICY rls_daily_stats_access ON daily_contributor_stats
        USING (
            current_setting('app.data_scope', true) = 'all'
            OR repository_id IN (
                SELECT id FROM repositories
                WHERE project_id::text = ANY(string_to_array(current_setting('app.current_project_ids', true), ','))
            )
            OR contributor_id::text = ANY(string_to_array(current_setting('app.current_contributor_ids', true), ','))
        )
    """)

    # Work items: accessible via project_id
    op.execute("""
        CREATE POLICY rls_work_item_access ON work_items
        USING (
            current_setting('app.data_scope', true) = 'all'
            OR project_id::text = ANY(string_to_array(current_setting('app.current_project_ids', true), ','))
        )
    """)


def downgrade() -> None:
    rls_tables = [
        "commits",
        "pull_requests",
        "reviews",
        "daily_contributor_stats",
        "repositories",
        "work_items",
    ]
    policy_names = {
        "commits": "rls_commit_access",
        "pull_requests": "rls_pr_access",
        "reviews": "rls_review_access",
        "daily_contributor_stats": "rls_daily_stats_access",
        "repositories": "rls_repo_access",
        "work_items": "rls_work_item_access",
    }
    for table in rls_tables:
        op.execute(f"DROP POLICY IF EXISTS {policy_names[table]} ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_table("project_memberships")
    op.drop_table("user_contributor_links")
    op.drop_table("access_audit_logs")
    op.drop_table("resource_grants")
    op.drop_table("access_policies")
