"""Seed data for the built-in Code Reviewer agent."""

from app.agents.builtin import BuiltinAgentSpec
from app.agents.prompts.defaults import CODE_REVIEWER_PROMPT

SPEC = BuiltinAgentSpec(
    slug="code-reviewer",
    name="Code Reviewer",
    description=(
        "Analyzes source code, PR diffs, file history, and blame. "
        "Provides code reviews, architecture analysis, and security observations "
        "using local git repositories and platform APIs."
    ),
    system_prompt=CODE_REVIEWER_PROMPT,
    tool_slugs=[
        "find_project",
        "find_repository",
        "list_directory",
        "read_file",
        "search_code",
        "get_commit_diff",
        "get_file_blame",
        "get_file_history",
        "get_pr_changed_files",
        "get_pr_file_diff",
        "get_pr_review_comments",
        "list_pull_requests",
    ],
)
