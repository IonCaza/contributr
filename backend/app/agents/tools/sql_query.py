"""Read-only SQL query tool with SELECT-only guardrail."""
from __future__ import annotations

import re
import logging

from langchain_core.tools import tool
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tools.base import ToolDefinition
from app.agents.tools.registry import register_tool_category

logger = logging.getLogger(__name__)

CATEGORY = "sql_query"

DEFINITIONS = [
    ToolDefinition(
        "run_sql_query",
        "Run SQL Query",
        "Execute a read-only SQL SELECT query against the database and return results. "
        "Only SELECT statements are allowed — no INSERT, UPDATE, DELETE, DROP, ALTER, "
        "TRUNCATE, CREATE, or other DDL/DML. Results are limited to 200 rows.",
        CATEGORY,
    ),
    ToolDefinition(
        "list_tables",
        "List Tables",
        "List all user-facing tables in the database with their descriptions.",
        CATEGORY,
    ),
    ToolDefinition(
        "describe_table",
        "Describe Table",
        "Show column names, types, and constraints for a specific table.",
        CATEGORY,
    ),
]

_FORBIDDEN_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|"
    r"COPY|VACUUM|REINDEX|CLUSTER|COMMENT\s+ON|SECURITY|SET\s+ROLE|"
    r"EXECUTE|CALL|DO\b|BEGIN|COMMIT|ROLLBACK|SAVEPOINT|LOCK)\b",
    re.IGNORECASE,
)

_MAX_ROWS = 200


def _validate_select_only(sql: str) -> str | None:
    """Return an error message if the query is not a pure SELECT, or None if OK."""
    stripped = sql.strip().rstrip(";").strip()
    if not stripped.upper().startswith("SELECT") and not stripped.upper().startswith("WITH"):
        return "Only SELECT (and WITH … SELECT) queries are allowed."
    match = _FORBIDDEN_PATTERN.search(stripped)
    if match:
        return f"Forbidden keyword detected: {match.group(0).upper()}. Only read-only queries are permitted."
    return None


def _build_tools(db: AsyncSession) -> list:

    @tool
    async def run_sql_query(sql: str) -> str:
        """Execute a read-only SQL SELECT query and return the results as a formatted table.

        Only SELECT statements are allowed. Results are limited to 200 rows.
        Use the knowledge graph context or list_tables/describe_table to understand
        the schema before writing queries.

        Args:
            sql: A SQL SELECT statement to execute.
        """
        error = _validate_select_only(sql)
        if error:
            return f"BLOCKED: {error}"

        limited_sql = sql.rstrip().rstrip(";")
        limited_sql = f"SELECT * FROM ({limited_sql}) AS _q LIMIT {_MAX_ROWS}"

        try:
            result = await db.execute(text(limited_sql))
            rows = result.fetchall()
            columns = list(result.keys())
        except Exception as exc:
            logger.warning("SQL query failed: %s — %s", sql, exc)
            return f"Query error: {exc}"

        if not rows:
            return "Query returned 0 rows."

        col_widths = [len(c) for c in columns]
        str_rows: list[list[str]] = []
        for row in rows:
            cells = [str(v) if v is not None else "NULL" for v in row]
            for i, cell in enumerate(cells):
                col_widths[i] = max(col_widths[i], len(cell))
            str_rows.append(cells)

        header = " | ".join(c.ljust(col_widths[i]) for i, c in enumerate(columns))
        sep = "-+-".join("-" * w for w in col_widths)
        body = "\n".join(
            " | ".join(cell.ljust(col_widths[i]) for i, cell in enumerate(row))
            for row in str_rows
        )
        footer = f"\n({len(rows)} row{'s' if len(rows) != 1 else ''})"
        if len(rows) == _MAX_ROWS:
            footer += f" — results capped at {_MAX_ROWS}"

        return f"{header}\n{sep}\n{body}{footer}"

    @tool
    async def list_tables() -> str:
        """List all user-facing database tables with their descriptions.

        Returns table names and comments set on each table in PostgreSQL.
        """
        query = text(
            "SELECT tablename, obj_description(pgc.oid, 'pg_class') AS description "
            "FROM pg_tables pt "
            "JOIN pg_class pgc ON pgc.relname = pt.tablename "
            "WHERE pt.schemaname = 'public' "
            "AND pt.tablename NOT IN ('alembic_version') "
            "ORDER BY pt.tablename"
        )
        try:
            result = await db.execute(query)
            rows = result.fetchall()
        except Exception as exc:
            return f"Error: {exc}"

        if not rows:
            return "No tables found."

        lines = []
        for row in rows:
            desc = row[1] or ""
            lines.append(f"- {row[0]}: {desc}" if desc else f"- {row[0]}")
        return "\n".join(lines)

    @tool
    async def describe_table(table_name: str) -> str:
        """Show the columns, types, and constraints for a given database table.

        Args:
            table_name: The exact table name (e.g. 'commits', 'pull_requests').
        """
        query = text(
            "SELECT c.column_name, c.data_type, c.is_nullable, "
            "  c.column_default, "
            "  col_description(pgc.oid, c.ordinal_position) AS description "
            "FROM information_schema.columns c "
            "JOIN pg_class pgc ON pgc.relname = c.table_name "
            "WHERE c.table_name = :table_name AND c.table_schema = 'public' "
            "ORDER BY c.ordinal_position"
        )
        try:
            result = await db.execute(query, {"table_name": table_name})
            rows = result.fetchall()
        except Exception as exc:
            return f"Error: {exc}"

        if not rows:
            return f"Table '{table_name}' not found or has no columns."

        lines = [f"Table: {table_name}", ""]
        for row in rows:
            col_name, dtype, nullable, default, desc = row
            parts = [f"  {col_name} ({dtype}"]
            if nullable == "NO":
                parts.append(", NOT NULL")
            if default:
                parts.append(f", default={default}")
            parts.append(")")
            if desc:
                parts.append(f" — {desc}")
            lines.append("".join(parts))
        return "\n".join(lines)

    return [run_sql_query, list_tables, describe_table]


register_tool_category(CATEGORY, DEFINITIONS, _build_tools)
