"""fix v1 presentation template import map to prevent dual React instances

The original v1 template used ?dev builds for React and ?bundle for Recharts,
which caused Recharts to bundle its own copy of React (production) while the
app used the dev build — two React instances means useContext crashes.

Fix: use production React everywhere and ?external on Recharts so it resolves
React through the import map (single instance).

Revision ID: i6j7k8l9m0n1
Revises: h5i6j7k8l9m0
Create Date: 2026-03-27
"""
from alembic import op
import sqlalchemy as sa

revision = "i6j7k8l9m0n1"
down_revision = "h5i6j7k8l9m0"
branch_labels = None
depends_on = None

OLD_IMPORTMAP = """  { "imports": {
    "react": "https://esm.sh/react@19?dev",
    "react/jsx-runtime": "https://esm.sh/react@19/jsx-runtime?dev",
    "react-dom/client": "https://esm.sh/react-dom@19/client?dev",
    "recharts": "https://esm.sh/recharts@3?bundle&deps=react@19,react-dom@19"
  }}"""

NEW_IMPORTMAP = """  { "imports": {
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
    if row and OLD_IMPORTMAP in row[1]:
        fixed = row[1].replace(OLD_IMPORTMAP, NEW_IMPORTMAP)
        conn.execute(
            sa.text("UPDATE presentation_templates SET template_html = :html WHERE id = :id"),
            {"html": fixed, "id": row[0]},
        )


def downgrade() -> None:
    pass
