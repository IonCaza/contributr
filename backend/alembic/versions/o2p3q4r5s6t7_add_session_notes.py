"""add session_notes and notes_token_cursor to chat_sessions

Revision ID: o2p3q4r5s6t7
Revises: n1o2p3q4r5s6
Create Date: 2026-04-01
"""
from alembic import op
import sqlalchemy as sa

revision = "o2p3q4r5s6t7"
down_revision = "n1o2p3q4r5s6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_sessions",
        sa.Column("session_notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "chat_sessions",
        sa.Column("notes_token_cursor", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("chat_sessions", "notes_token_cursor")
    op.drop_column("chat_sessions", "session_notes")
