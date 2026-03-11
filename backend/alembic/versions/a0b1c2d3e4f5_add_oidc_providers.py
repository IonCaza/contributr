"""add OIDC providers, user OIDC columns, auth settings local login toggle

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "a0b1c2d3e4f5"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oidc_providers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(100), unique=True, index=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("provider_type", sa.String(50), nullable=False),
        sa.Column("client_id", sa.String(512), nullable=False),
        sa.Column("client_secret_encrypted", sa.Text(), nullable=False, server_default=""),
        sa.Column("discovery_url", sa.String(2048), nullable=True),
        sa.Column("authorization_url", sa.String(2048), nullable=False, server_default=""),
        sa.Column("token_url", sa.String(2048), nullable=False, server_default=""),
        sa.Column("userinfo_url", sa.String(2048), nullable=True),
        sa.Column("jwks_url", sa.String(2048), nullable=False, server_default=""),
        sa.Column("scopes", sa.String(500), nullable=False, server_default="openid profile email"),
        sa.Column("claim_mapping", JSONB, nullable=False, server_default='{"email":"email","name":"name","groups":"groups","admin_groups":[]}'),
        sa.Column("auto_provision", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        comment="Configured OIDC/OAuth2 identity providers.",
    )

    op.add_column("users", sa.Column("oidc_provider_id", UUID(as_uuid=True), sa.ForeignKey("oidc_providers.id", ondelete="SET NULL"), nullable=True))
    op.add_column("users", sa.Column("oidc_subject", sa.String(255), nullable=True))
    op.create_unique_constraint("uq_user_oidc_identity", "users", ["oidc_provider_id", "oidc_subject"])

    op.alter_column("users", "hashed_password", nullable=True)

    op.add_column("auth_settings", sa.Column("local_login_enabled", sa.Boolean(), nullable=False, server_default="true"))


def downgrade() -> None:
    op.drop_column("auth_settings", "local_login_enabled")

    op.alter_column("users", "hashed_password", nullable=False)

    op.drop_constraint("uq_user_oidc_identity", "users", type_="unique")
    op.drop_column("users", "oidc_subject")
    op.drop_column("users", "oidc_provider_id")

    op.drop_table("oidc_providers")
