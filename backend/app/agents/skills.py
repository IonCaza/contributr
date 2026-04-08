"""Skill loading and seeding for the agent prompt extension system."""

from __future__ import annotations

import logging

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent_skill import AgentSkill

logger = logging.getLogger(__name__)


async def load_active_skills(agent_slug: str, db: AsyncSession) -> str:
    """Load auto-inject skills matching *agent_slug* and return formatted prompt sections."""
    result = await db.scalars(
        select(AgentSkill).where(
            AgentSkill.is_active.is_(True),
            AgentSkill.auto_inject.is_(True),
            or_(
                AgentSkill.applicable_agents.is_(None),
                AgentSkill.applicable_agents.contains([agent_slug]),
            ),
        )
    )
    skills = result.all()
    if not skills:
        return ""
    sections = [f"## Skill: {s.name}\n{s.prompt_content}" for s in skills]
    return "\n\n---\n\n".join(sections)


async def list_available_skills(agent_slug: str, db: AsyncSession) -> list[dict]:
    """Return non-auto-inject skills available to an agent (for the use_skill tool)."""
    result = await db.scalars(
        select(AgentSkill).where(
            AgentSkill.is_active.is_(True),
            AgentSkill.auto_inject.is_(False),
            or_(
                AgentSkill.applicable_agents.is_(None),
                AgentSkill.applicable_agents.contains([agent_slug]),
            ),
        )
    )
    return [
        {"slug": s.slug, "name": s.name, "description": s.description or ""}
        for s in result.all()
    ]


BUILTIN_SKILLS: list[dict] = [
    {
        "slug": "dashboard-layout-patterns",
        "name": "Dashboard Layout Patterns",
        "description": "Common dashboard layout patterns and when to use each",
        "applicable_agents": ["presentation-designer"],
        "auto_inject": False,
        "prompt_content": """\
Common dashboard layout patterns and guidance for choosing the right one.

### KPI Row + Trend Charts + Detail Table
Best for: executive overviews, sprint reports, team health dashboards.
- Top row: 3-5 MetricCard components showing headline numbers
- Middle: 1-2 line/area charts showing trends over time
- Bottom: sortable table with drill-down rows
- Grid: `grid-cols-3 lg:grid-cols-5` for KPIs, full-width for charts

### Comparison Grid
Best for: contributor comparisons, team vs team, sprint vs sprint.
- Side-by-side panels with mirrored metrics
- Use bar charts for direct comparison, radar charts for multi-dimensional
- Highlight deltas with color (green = improvement, red = regression)

### Drill-Down Hierarchy
Best for: backlog analysis, file ownership, dependency trees.
- Start with summary aggregates
- Progressive disclosure: click a category to expand details
- Use `useState` to track expanded sections

### Time-Series Focus
Best for: velocity trends, cumulative flow, burndown charts.
- Single prominent chart taking 60%+ of viewport
- Supporting metric cards above or beside
- Use `Brush` component for date range selection on long histories

### Responsive Grid Rules
- Mobile (< 640px): single column stack
- Tablet (640-1024px): 2 columns
- Desktop (> 1024px): 3-4 columns
- Charts: always full-width or 2-column span minimum
- MetricCards: smallest useful unit, pack tightly""",
    },
    {
        "slug": "data-exploration-workflow",
        "name": "Data Exploration Workflow",
        "description": "Systematic approach to discovering and validating data before building visualizations",
        "applicable_agents": ["presentation-designer"],
        "auto_inject": False,
        "prompt_content": """\
Systematic data exploration workflow. Follow these steps BEFORE writing any component code.

### Step 1: Schema Discovery
Call `list_tables` to see all available tables. Then call `describe_table` for
each table that looks relevant to the user's request. Record exact column names
and types -- you will need them for queries.

### Step 2: Sample Data
For each relevant table, run `run_sql_query` with `LIMIT 5` to see actual data
shapes. Pay attention to:
- NULL frequency in important columns
- Date formats and ranges
- Enum values (states, statuses, types)
- Foreign key patterns

### Step 3: Aggregation Probes
Run aggregate queries to understand data volume and distribution:
- `COUNT(*)` per table
- `MIN/MAX` on date columns (to know the time range)
- `COUNT(DISTINCT ...)` on key dimensions
- `GROUP BY` on categorical columns to see cardinality

### Step 4: Anomaly Check
Before building charts, verify the data makes sense:
- Are there gaps in time series? (missing days/sprints)
- Are there outliers that would skew averages?
- Is there enough data for meaningful trends? (< 3 data points = warn user)

### Step 5: Query Plan
Document the exact queries you will use in the presentation:
- Write the SQL and test it via `run_sql_query`
- Confirm column names match the schema (NEVER guess)
- Verify result shapes match what your charts expect""",
    },
    {
        "slug": "chart-type-selector",
        "name": "Chart Type Selection Guide",
        "description": "Decision tree for choosing the right chart type based on data characteristics",
        "applicable_agents": ["presentation-designer"],
        "auto_inject": False,
        "prompt_content": """\
Chart type selection guide based on data characteristics and intent.

### Time Series → LineChart or AreaChart
- **LineChart**: comparing multiple series, emphasizing rate of change
- **AreaChart**: showing cumulative totals or composition over time
- Use `Brush` for long time ranges (> 20 data points)
- Add `ReferenceLine` for targets or averages

### Comparisons → BarChart
- **Vertical bars**: comparing categories (teams, repos, contributors)
- **Horizontal bars**: when labels are long (file paths, PR titles)
- **Stacked bars**: showing composition within each category
- Sort by value (largest first) unless there's a natural order

### Proportions → PieChart or Treemap
- **PieChart**: 2-6 slices only. More than 6 → group into "Other"
- **Treemap**: hierarchical proportions (file ownership, category breakdown)
- Always include absolute values alongside percentages

### Distributions → Histogram (BarChart with bins)
- Cycle time distribution, PR size distribution
- Use consistent bin widths
- Mark median/p75/p90 with `ReferenceLine`

### Correlations → ScatterChart
- Two continuous variables (velocity vs team size, churn vs bugs)
- Add trend line when meaningful

### Multi-Dimensional → RadarChart
- Comparing 3+ metrics for a single entity or small group
- Normalize all axes to 0-1 or 0-100 scale
- Max 3 overlaid series for readability

### Progress → RadialBar or simple bar
- Sprint completion, backlog clearance
- Use color gradients (red → yellow → green) for health indication

### Single Values → MetricCard
- Current velocity, total items, completion percentage
- Add subtitle for context (trend, comparison to average)""",
    },
]


async def seed_builtin_skills(db: AsyncSession) -> None:
    """Upsert builtin skills. Existing skills get their prompt_content updated."""
    changed = False
    for spec in BUILTIN_SKILLS:
        result = await db.execute(
            select(AgentSkill).where(AgentSkill.slug == spec["slug"])
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            db.add(AgentSkill(
                slug=spec["slug"],
                name=spec["name"],
                description=spec.get("description"),
                prompt_content=spec["prompt_content"],
                applicable_agents=spec.get("applicable_agents"),
                auto_inject=spec.get("auto_inject", False),
                is_active=True,
            ))
            changed = True
            logger.info("Seeded builtin skill: %s", spec["slug"])
        elif existing.prompt_content != spec["prompt_content"]:
            existing.prompt_content = spec["prompt_content"]
            existing.name = spec["name"]
            existing.description = spec.get("description")
            changed = True
            logger.info("Updated builtin skill: %s", spec["slug"])
    if changed:
        await db.commit()
