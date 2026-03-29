"""add presentation_templates, presentations, presentation_versions tables

Revision ID: h5i6j7k8l9m0
Revises: b4c5d6e7f8a9
Create Date: 2026-03-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "h5i6j7k8l9m0"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None

V1_TEMPLATE_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <script src="https://cdn.tailwindcss.com"></script>
  <script type="importmap">
  { "imports": {
    "react": "https://esm.sh/react@19",
    "react/": "https://esm.sh/react@19/",
    "react-dom": "https://esm.sh/react-dom@19",
    "react-dom/": "https://esm.sh/react-dom@19/",
    "recharts": "https://esm.sh/recharts@3?external=react,react-dom"
  }}
  </script>
  <style>
    body { margin: 0; }
    .contributr-loading { display: flex; align-items: center; justify-content: center; min-height: 100vh; }
    .contributr-error { color: #fca5a5; background: rgba(127,29,29,0.3); border: 1px solid #7f1d1d; border-radius: 12px; padding: 16px; margin: 16px; }
  </style>
</head>
<body class="bg-gray-950 text-white">
  <div id="root"><div class="contributr-loading"><p style="color:#6b7280">Loading presentation&hellip;</p></div></div>
  <script type="module">
    import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
    import { createRoot } from "react-dom/client";
    import {
      ResponsiveContainer, BarChart, Bar, LineChart, Line, AreaChart, Area,
      PieChart, Pie, Cell, RadarChart, Radar, PolarGrid, PolarAngleAxis,
      PolarRadiusAxis, ScatterChart, Scatter, ComposedChart, RadialBarChart,
      RadialBar, Treemap, FunnelChart, Funnel, XAxis, YAxis, ZAxis,
      CartesianGrid, Tooltip, Legend, Brush, ReferenceLine, ReferenceArea,
      Label, LabelList
    } from "recharts";

    // Namespace alias so code using `Recharts.BarChart` also works.
    const Recharts = {
      ResponsiveContainer, BarChart, Bar, LineChart, Line, AreaChart, Area,
      PieChart, Pie, Cell, RadarChart, Radar, PolarGrid, PolarAngleAxis,
      PolarRadiusAxis, ScatterChart, Scatter, ComposedChart, RadialBarChart,
      RadialBar, Treemap, FunnelChart, Funnel, XAxis, YAxis, ZAxis,
      CartesianGrid, Tooltip, Legend, Brush, ReferenceLine, ReferenceArea,
      Label, LabelList,
    };

    // ── Contributr Data Bridge (protocol v1) ──────────────────────────
    const BRIDGE_PROTOCOL_VERSION = 1;

    const contributr = {
      async query(tool, params) {
        const id = crypto.randomUUID();
        return new Promise((resolve, reject) => {
          const timeout = setTimeout(() => {
            window.removeEventListener("message", handler);
            reject(new Error("Bridge query timed out after 30s"));
          }, 30000);
          const handler = (e) => {
            if (e.data?.id === id) {
              clearTimeout(timeout);
              window.removeEventListener("message", handler);
              if (e.data.error) reject(new Error(e.data.error));
              else resolve(e.data.result);
            }
          };
          window.addEventListener("message", handler);
          window.parent.postMessage(
            { type: "contributr_query", v: BRIDGE_PROTOCOL_VERSION, id, tool, params },
            "*"
          );
        });
      },
    };

    // ── React Hooks ───────────────────────────────────────────────────
    function useQuery(tool, params) {
      const [state, setState] = useState({ data: null, loading: true, error: null });
      const key = JSON.stringify([tool, params]);
      useEffect(() => {
        let cancelled = false;
        setState({ data: null, loading: true, error: null });
        contributr.query(tool, params)
          .then((data) => { if (!cancelled) setState({ data, loading: false, error: null }); })
          .catch((error) => { if (!cancelled) setState({ data: null, loading: false, error }); });
        return () => { cancelled = true; };
      }, [key]);
      return state;
    }

    function useMultiQuery(queries) {
      const [results, setResults] = useState({});
      const [loading, setLoading] = useState(true);
      const [error, setError] = useState(null);
      const key = JSON.stringify(queries);
      useEffect(() => {
        let cancelled = false;
        setLoading(true);
        const entries = Object.entries(queries);
        Promise.all(entries.map(([_, [tool, params]]) => contributr.query(tool, params)))
          .then((values) => {
            if (cancelled) return;
            const obj = {};
            entries.forEach(([k], i) => { obj[k] = values[i]; });
            setResults(obj);
            setLoading(false);
          })
          .catch((err) => { if (!cancelled) { setError(err); setLoading(false); } });
        return () => { cancelled = true; };
      }, [key]);
      return { results, loading, error };
    }

    // ── Utility Components ────────────────────────────────────────────
    function Skeleton({ className = "h-64", children }) {
      return React.createElement("div", {
        className: "animate-pulse bg-gray-800/50 rounded-xl " + className,
      }, children);
    }

    function MetricCard({ label, value, subtitle, icon }) {
      return React.createElement("div", { className: "bg-gray-900/50 backdrop-blur rounded-xl p-6 border border-gray-800" },
        React.createElement("p", { className: "text-sm font-medium text-gray-400 uppercase tracking-wider" }, label),
        React.createElement("p", { className: "text-3xl font-bold mt-1 tracking-tight" }, value),
        subtitle && React.createElement("p", { className: "text-sm text-gray-500 mt-1" }, subtitle)
      );
    }

    function ErrorCard({ message, onRetry }) {
      return React.createElement("div", { className: "contributr-error" },
        React.createElement("p", { className: "font-medium" }, "Something went wrong"),
        React.createElement("p", { className: "text-sm mt-1 text-red-300/80" }, String(message)),
        onRetry && React.createElement("button", {
          onClick: onRetry,
          className: "mt-3 text-sm px-3 py-1 rounded bg-red-900/50 hover:bg-red-900/80 transition-colors",
        }, "Retry")
      );
    }

    function Section({ title, children, className = "" }) {
      return React.createElement("section", { className: "space-y-4 " + className },
        title && React.createElement("h2", { className: "text-xl font-semibold tracking-tight" }, title),
        children
      );
    }

    // ── Agent-Generated Code (injected at render time) ────────────────
    /* __COMPONENT_CODE__ */

    // ── Mount ─────────────────────────────────────────────────────────
    const root = createRoot(document.getElementById("root"));
    root.render(React.createElement(App));
  </script>
</body>
</html>"""


def upgrade() -> None:
    op.create_table(
        "presentation_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("version", sa.Integer, nullable=False, unique=True),
        sa.Column("template_html", sa.Text, nullable=False),
        sa.Column("description", sa.String(1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        comment="Immutable versioned HTML templates for presentation rendering.",
    )
    op.create_index("ix_presentation_templates_version", "presentation_templates", ["version"])

    op.create_table(
        "presentations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(1024), nullable=False),
        sa.Column("description", sa.String(4096), nullable=True),
        sa.Column("component_code", sa.Text, nullable=False, server_default=""),
        sa.Column("template_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("prompt", sa.Text, nullable=False, server_default=""),
        sa.Column("chat_session_id", UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        comment="AI-generated dashboard presentations with component code and template version reference.",
    )
    op.create_index("ix_presentations_project_id", "presentations", ["project_id"])

    op.create_table(
        "presentation_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("presentation_id", UUID(as_uuid=True), sa.ForeignKey("presentations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("component_code", sa.Text, nullable=False),
        sa.Column("template_version", sa.Integer, nullable=False),
        sa.Column("change_summary", sa.String(1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        comment="Version history tracking component code and template version at each presentation save.",
    )
    op.create_index("ix_presentation_versions_presentation_id", "presentation_versions", ["presentation_id"])

    op.execute(
        sa.text(
            "INSERT INTO presentation_templates (id, version, template_html, description) "
            "VALUES (gen_random_uuid(), 1, :html, 'Initial v1 template with bridge protocol v1, useQuery, useMultiQuery, Skeleton, MetricCard, ErrorCard, Section')"
        ).bindparams(html=V1_TEMPLATE_HTML)
    )


def downgrade() -> None:
    op.drop_index("ix_presentation_versions_presentation_id", table_name="presentation_versions")
    op.drop_table("presentation_versions")
    op.drop_index("ix_presentations_project_id", table_name="presentations")
    op.drop_table("presentations")
    op.drop_index("ix_presentation_templates_version", table_name="presentation_templates")
    op.drop_table("presentation_templates")
