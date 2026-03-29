"""add Recharts namespace alias to v1 template

Agent-generated code sometimes references ``Recharts.BarChart`` instead of
using the pre-imported ``BarChart`` directly.  Adding a ``Recharts``
namespace object makes both access patterns work.

Revision ID: k8l9m0n1o2p3
Revises: j7k8l9m0n1o2
Create Date: 2026-03-27
"""
from alembic import op
import sqlalchemy as sa

revision = "k8l9m0n1o2p3"
down_revision = "j7k8l9m0n1o2"
branch_labels = None
depends_on = None

MARKER = '    } from "recharts";'

NAMESPACE_BLOCK = """
    // Namespace alias so code using `Recharts.BarChart` also works.
    const Recharts = {
      ResponsiveContainer, BarChart, Bar, LineChart, Line, AreaChart, Area,
      PieChart, Pie, Cell, RadarChart, Radar, PolarGrid, PolarAngleAxis,
      PolarRadiusAxis, ScatterChart, Scatter, ComposedChart, RadialBarChart,
      RadialBar, Treemap, FunnelChart, Funnel, XAxis, YAxis, ZAxis,
      CartesianGrid, Tooltip, Legend, Brush, ReferenceLine, ReferenceArea,
      Label, LabelList,
    };"""


def upgrade() -> None:
    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT id, template_html FROM presentation_templates WHERE version = 1")
    ).fetchone()
    if row and MARKER in row[1] and "const Recharts" not in row[1]:
        fixed = row[1].replace(MARKER, MARKER + NAMESPACE_BLOCK)
        conn.execute(
            sa.text("UPDATE presentation_templates SET template_html = :html WHERE id = :id"),
            {"html": fixed, "id": row[0]},
        )


def downgrade() -> None:
    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT id, template_html FROM presentation_templates WHERE version = 1")
    ).fetchone()
    if row and NAMESPACE_BLOCK in row[1]:
        fixed = row[1].replace(NAMESPACE_BLOCK, "")
        conn.execute(
            sa.text("UPDATE presentation_templates SET template_html = :html WHERE id = :id"),
            {"html": fixed, "id": row[0]},
        )
