"""add table comments

Revision ID: l7m8n9o0p1q2
Revises: k6l7m8n9o0p1
Create Date: 2026-03-05
"""
from alembic import op

revision = "l7m8n9o0p1q2"
down_revision = "k6l7m8n9o0p1"
branch_labels = None
depends_on = None

TABLE_COMMENTS: dict[str, str] = {
    "projects": "Top-level grouping that organizes repositories and contributors. Each project tracks code contributions across one or more repositories.",
    "repositories": "Git repository registered for contribution tracking. Stores clone URLs, platform type (GitHub/GitLab/Azure DevOps), and sync metadata.",
    "contributors": "Unified contributor identity that aggregates commits, pull requests, and reviews across repositories. Supports multiple email aliases and platform usernames.",
    "contributor_aliases": "Alternate email or name mapping to a canonical contributor, used to merge contributions from the same person using different Git identities.",
    "commits": "Individual Git commit with authoring metadata, code churn statistics (lines added, deleted, files changed), and merge flag.",
    "commit_files": "Per-file change record within a commit. Tracks the file path and line-level additions and deletions.",
    "pull_requests": "Pull/merge request with lifecycle timestamps, review metrics (iteration count, comment count), and current state (open/merged/closed).",
    "reviews": "Code review submitted on a pull request. Tracks reviewer identity, review verdict (approved/changes_requested/commented), and timing.",
    "branches": "Git branch within a repository, linked to commits via the commit_branches association.",
    "commit_branches": "Association table linking commits to branches they appear on.",
    "daily_contributor_stats": "Pre-aggregated daily metrics per contributor per repository, including commits, lines changed, PRs, reviews, and comments.",
    "sync_jobs": "Background repository sync task. Records status (queued/running/completed/failed), timing, and error details.",
    "file_exclusion_patterns": "Glob patterns for excluding files and directories from contribution analysis (e.g., vendor/, *.lock, *.min.js).",
    "users": "Application user account with authentication credentials and admin flag.",
    "ssh_credentials": "Encrypted SSH key pair used for cloning Git repositories over SSH.",
    "platform_credentials": "Encrypted API token for accessing platform APIs (GitHub, GitLab, Azure DevOps).",
    "project_contributors": "Association table linking projects to their contributors.",
    "ai_settings": "Single-row global toggle controlling whether AI features are enabled.",
    "llm_providers": "LLM provider configuration including model name, API key, base URL, temperature, and optional context window.",
    "agents": "AI agent definition with system prompt, assigned tools, LLM provider, and iteration limits.",
    "agent_tool_assignments": "Join table linking agents to their enabled tools.",
    "knowledge_graphs": "Knowledge graph storing structured data model context (schema, entities, relationships) for AI agent prompt injection.",
    "agent_knowledge_graph_assignments": "Join table linking agents to knowledge graphs they use as context.",
    "chat_sessions": "User conversation thread with an AI agent, including running context summary for token management.",
    "chat_messages": "Individual message in a chat session with role (user/assistant/tool) and content.",
}


def upgrade() -> None:
    for table, comment in TABLE_COMMENTS.items():
        escaped = comment.replace("'", "''")
        op.execute(f"COMMENT ON TABLE {table} IS '{escaped}'")


def downgrade() -> None:
    for table in TABLE_COMMENTS:
        op.execute(f"COMMENT ON TABLE {table} IS NULL")
