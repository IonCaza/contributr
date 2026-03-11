"""add ai memory settings columns

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "b3c4d5e6f7a8"
down_revision = ("a2b3c4d5e6f7", "a0b1c2d3e4f5")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_settings", sa.Column("memory_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("ai_settings", sa.Column("memory_embedding_provider_id", UUID(as_uuid=True), nullable=True))
    op.add_column("ai_settings", sa.Column("extraction_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("ai_settings", sa.Column("extraction_provider_id", UUID(as_uuid=True), nullable=True))
    op.add_column("ai_settings", sa.Column("extraction_enable_inserts", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("ai_settings", sa.Column("extraction_enable_updates", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("ai_settings", sa.Column("extraction_enable_deletes", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("ai_settings", sa.Column("cleanup_threshold_ratio", sa.Float(), nullable=False, server_default=sa.text("0.6")))
    op.add_column("ai_settings", sa.Column("summary_token_ratio", sa.Float(), nullable=False, server_default=sa.text("0.04")))

    op.create_foreign_key(
        "fk_ai_settings_memory_embedding_provider",
        "ai_settings", "llm_providers",
        ["memory_embedding_provider_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_ai_settings_extraction_provider",
        "ai_settings", "llm_providers",
        ["extraction_provider_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_ai_settings_extraction_provider", "ai_settings", type_="foreignkey")
    op.drop_constraint("fk_ai_settings_memory_embedding_provider", "ai_settings", type_="foreignkey")
    op.drop_column("ai_settings", "summary_token_ratio")
    op.drop_column("ai_settings", "cleanup_threshold_ratio")
    op.drop_column("ai_settings", "extraction_enable_deletes")
    op.drop_column("ai_settings", "extraction_enable_updates")
    op.drop_column("ai_settings", "extraction_enable_inserts")
    op.drop_column("ai_settings", "extraction_provider_id")
    op.drop_column("ai_settings", "extraction_enabled")
    op.drop_column("ai_settings", "memory_embedding_provider_id")
    op.drop_column("ai_settings", "memory_enabled")
