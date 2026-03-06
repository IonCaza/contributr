"""Seed data for the built-in Text-to-SQL agent."""

from app.agents.builtin import BuiltinAgentSpec
from app.agents.prompts.defaults import TEXT_TO_SQL_PROMPT

SPEC = BuiltinAgentSpec(
    slug="text-to-sql",
    name="Text to SQL",
    description=(
        "Translates natural-language questions into SQL SELECT queries, "
        "executes them against the database, and presents results. "
        "Read-only — no data modifications allowed. "
        "Assign a knowledge graph to give this agent schema context."
    ),
    system_prompt=TEXT_TO_SQL_PROMPT,
    tool_slugs=[
        "run_sql_query",
        "list_tables",
        "describe_table",
    ],
)
