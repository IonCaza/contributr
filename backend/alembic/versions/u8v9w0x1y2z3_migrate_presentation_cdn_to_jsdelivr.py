"""migrate presentation template CDN from esm.sh to cdn.jsdelivr.net

Now reverted by v9w0x1y2z3a4 — kept only so alembic can locate the
revision in its history chain.

Revision ID: u8v9w0x1y2z3
Revises: t7u8v9w0x1y2
Create Date: 2026-04-13
"""
from alembic import op
import sqlalchemy as sa

revision = "u8v9w0x1y2z3"
down_revision = "t7u8v9w0x1y2"
branch_labels = None
depends_on = None

OLD_TAILWIND = '<script src="https://cdn.tailwindcss.com"></script>'
NEW_TAILWIND = '<script src="https://cdn.jsdelivr.net/npm/tailwindcss-cdn@3"></script>'

OLD_IMPORTMAP = """\
  { "imports": {
    "react": "https://esm.sh/react@19",
    "react/": "https://esm.sh/react@19/",
    "react-dom": "https://esm.sh/react-dom@19",
    "react-dom/": "https://esm.sh/react-dom@19/",
    "recharts": "https://esm.sh/recharts@3?external=react,react-dom"
  }}"""

NEW_IMPORTMAP = """\
  { "imports": {
    "react": "https://cdn.jsdelivr.net/npm/react@19.2.4/+esm",
    "react-dom/client": "https://cdn.jsdelivr.net/npm/react-dom@19.2.4/client/+esm",
    "recharts": "https://cdn.jsdelivr.net/npm/recharts@3/+esm"
  }}"""


def upgrade() -> None:
    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT id, template_html FROM presentation_templates WHERE version = 1")
    ).fetchone()
    if not row:
        return
    html = row[1]
    html = html.replace(OLD_TAILWIND, NEW_TAILWIND)
    html = html.replace(OLD_IMPORTMAP, NEW_IMPORTMAP)
    conn.execute(
        sa.text("UPDATE presentation_templates SET template_html = :html WHERE id = :id"),
        {"html": html, "id": row[0]},
    )


def downgrade() -> None:
    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT id, template_html FROM presentation_templates WHERE version = 1")
    ).fetchone()
    if not row:
        return
    html = row[1]
    html = html.replace(NEW_TAILWIND, OLD_TAILWIND)
    html = html.replace(NEW_IMPORTMAP, OLD_IMPORTMAP)
    conn.execute(
        sa.text("UPDATE presentation_templates SET template_html = :html WHERE id = :id"),
        {"html": html, "id": row[0]},
    )
