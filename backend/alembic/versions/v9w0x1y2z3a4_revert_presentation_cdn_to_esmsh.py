"""revert presentation template CDN back to esm.sh

The CSP on Azure Application Gateway has been updated to allow esm.sh
and cdn.tailwindcss.com directly.  Revert the jsdelivr migration
(u8v9w0x1y2z3) so the template uses esm.sh again, which correctly
handles single-React-instance via ?external=react,react-dom.

Revision ID: v9w0x1y2z3a4
Revises: u8v9w0x1y2z3
Create Date: 2026-04-13
"""
from alembic import op
import sqlalchemy as sa

revision = "v9w0x1y2z3a4"
down_revision = "u8v9w0x1y2z3"
branch_labels = None
depends_on = None

JSDELIVR_TAILWIND = '<script src="https://cdn.jsdelivr.net/npm/tailwindcss-cdn@3"></script>'
ESMSH_TAILWIND = '<script src="https://cdn.tailwindcss.com"></script>'

JSDELIVR_IMPORTMAP = """\
  { "imports": {
    "react": "https://cdn.jsdelivr.net/npm/react@19.2.4/+esm",
    "react-dom/client": "https://cdn.jsdelivr.net/npm/react-dom@19.2.4/client/+esm",
    "recharts": "https://cdn.jsdelivr.net/npm/recharts@3/+esm"
  }}"""

ESMSH_IMPORTMAP = """\
  { "imports": {
    "react": "https://esm.sh/react@19",
    "react/": "https://esm.sh/react@19/",
    "react-dom": "https://esm.sh/react-dom@19",
    "react-dom/": "https://esm.sh/react-dom@19/",
    "recharts": "https://esm.sh/recharts@3?external=react,react-dom"
  }}"""


def upgrade() -> None:
    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT id, template_html FROM presentation_templates WHERE version = 1")
    ).fetchone()
    if not row:
        return
    html = row[1]
    html = html.replace(JSDELIVR_TAILWIND, ESMSH_TAILWIND)
    html = html.replace(JSDELIVR_IMPORTMAP, ESMSH_IMPORTMAP)
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
    html = html.replace(ESMSH_TAILWIND, JSDELIVR_TAILWIND)
    html = html.replace(ESMSH_IMPORTMAP, JSDELIVR_IMPORTMAP)
    conn.execute(
        sa.text("UPDATE presentation_templates SET template_html = :html WHERE id = :id"),
        {"html": html, "id": row[0]},
    )
