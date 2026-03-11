"""add MFA, SMTP, email templates, and auth settings

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- User table: MFA / auth provider columns ---
    op.add_column("users", sa.Column("auth_provider", sa.String(50), nullable=False, server_default="local"))
    op.add_column("users", sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("users", sa.Column("mfa_method", sa.String(20), nullable=True))
    op.add_column("users", sa.Column("totp_secret_encrypted", sa.String(2048), nullable=True))
    op.add_column("users", sa.Column("mfa_recovery_codes_encrypted", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("mfa_setup_complete", sa.Boolean(), nullable=False, server_default=sa.text("false")))

    # --- SMTP settings singleton ---
    op.create_table(
        "smtp_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("host", sa.String(255), nullable=False, server_default=""),
        sa.Column("port", sa.Integer(), nullable=False, server_default="587"),
        sa.Column("username", sa.String(255), nullable=False, server_default=""),
        sa.Column("password_encrypted", sa.String(2048), nullable=False, server_default=""),
        sa.Column("from_email", sa.String(320), nullable=False, server_default=""),
        sa.Column("from_name", sa.String(255), nullable=False, server_default="Contributr"),
        sa.Column("use_tls", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        comment="Single-row SMTP configuration for sending outbound emails.",
    )

    # --- Email templates ---
    op.create_table(
        "email_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(100), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("variables", JSONB(), nullable=False, server_default="{}"),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        comment="Jinja2-based email templates that admins can customise.",
    )

    # --- Auth settings singleton ---
    op.create_table(
        "auth_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("force_mfa_local_auth", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        comment="Single-row global authentication/MFA policy settings.",
    )


def downgrade() -> None:
    op.drop_table("auth_settings")
    op.drop_table("email_templates")
    op.drop_table("smtp_settings")
    op.drop_column("users", "mfa_setup_complete")
    op.drop_column("users", "mfa_recovery_codes_encrypted")
    op.drop_column("users", "totp_secret_encrypted")
    op.drop_column("users", "mfa_method")
    op.drop_column("users", "mfa_enabled")
    op.drop_column("users", "auth_provider")
