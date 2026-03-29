"""pre-import recharts in v1 template to prevent undefined component errors

Agent-generated code relied on its own `import { ... } from "recharts"` which
can fail depending on ESM CDN resolution. Fix: import all common Recharts
components in the template itself so they are always available as module-scope
variables.

Revision ID: j7k8l9m0n1o2
Revises: i6j7k8l9m0n1
Create Date: 2026-03-27
"""
from alembic import op
import sqlalchemy as sa

revision = "j7k8l9m0n1o2"
down_revision = "i6j7k8l9m0n1"
branch_labels = None
depends_on = None

OLD_IMPORTS = """\
    import React, { useState, useEffect, useCallback, useMemo } from "react";
    import { createRoot } from "react-dom/client";"""

NEW_IMPORTS = """\
    import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
    import { createRoot } from "react-dom/client";
    import {
      ResponsiveContainer, BarChart, Bar, LineChart, Line, AreaChart, Area,
      PieChart, Pie, Cell, RadarChart, Radar, PolarGrid, PolarAngleAxis,
      PolarRadiusAxis, ScatterChart, Scatter, ComposedChart, RadialBarChart,
      RadialBar, Treemap, FunnelChart, Funnel, XAxis, YAxis, ZAxis,
      CartesianGrid, Tooltip, Legend, Brush, ReferenceLine, ReferenceArea,
      Label, LabelList
    } from "recharts";"""


def upgrade() -> None:
    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT id, template_html FROM presentation_templates WHERE version = 1")
    ).fetchone()
    if row and OLD_IMPORTS in row[1]:
        fixed = row[1].replace(OLD_IMPORTS, NEW_IMPORTS)
        conn.execute(
            sa.text("UPDATE presentation_templates SET template_html = :html WHERE id = :id"),
            {"html": fixed, "id": row[0]},
        )


def downgrade() -> None:
    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT id, template_html FROM presentation_templates WHERE version = 1")
    ).fetchone()
    if row and NEW_IMPORTS in row[1]:
        fixed = row[1].replace(NEW_IMPORTS, OLD_IMPORTS)
        conn.execute(
            sa.text("UPDATE presentation_templates SET template_html = :html WHERE id = :id"),
            {"html": fixed, "id": row[0]},
        )
