"""add column comments

Revision ID: m8n9o0p1q2r3
Revises: l7m8n9o0p1q2
Create Date: 2026-03-05
"""
from alembic import op

revision = "m8n9o0p1q2r3"
down_revision = "l7m8n9o0p1q2"
branch_labels = None
depends_on = None

COLUMN_COMMENTS: dict[str, dict[str, str]] = {
    "projects": {
        "id": "Auto-generated unique identifier",
        "name": "Human-readable project name, must be unique",
        "description": "Optional free-text project description",
        "created_at": "Timestamp when the project was created",
        "platform_credential_id": "API credential used for syncing repositories in this project",
        "updated_at": "Timestamp of the last modification",
    },
    "project_contributors": {
        "project_id": "Parent project",
        "contributor_id": "Associated contributor",
    },
    "repositories": {
        "id": "Auto-generated unique identifier",
        "project_id": "Parent project this repository belongs to",
        "name": "Repository name as it appears on the hosting platform",
        "clone_url": "HTTPS clone URL",
        "ssh_url": "SSH clone URL",
        "platform": "Source code hosting platform (github, gitlab, azure)",
        "platform_owner": "Organization or user that owns the repo on the platform",
        "platform_repo": "Repository name on the platform (may differ from display name)",
        "default_branch": "Name of the default/main branch (e.g. main, master)",
        "ssh_credential_id": "SSH key used for cloning, if applicable",
        "last_synced_at": "Timestamp of the most recent successful data sync",
        "created_at": "Timestamp when the repository was registered",
    },
    "contributors": {
        "id": "Auto-generated unique identifier",
        "canonical_name": "Primary display name for the contributor",
        "canonical_email": "Primary email address, used as the unique identity key",
        "alias_emails": "Additional email addresses associated with this contributor",
        "alias_names": "Additional names associated with this contributor",
        "github_username": "GitHub platform username",
        "gitlab_username": "GitLab platform username",
        "azure_username": "Azure DevOps platform username",
        "created_at": "Timestamp when the contributor was first detected",
    },
    "contributor_aliases": {
        "id": "Auto-generated unique identifier",
        "contributor_id": "Canonical contributor this alias belongs to",
        "email": "Alternate email address that maps to the canonical contributor",
        "name": "Alternate name associated with this email alias",
    },
    "commits": {
        "id": "Auto-generated unique identifier",
        "repository_id": "Repository this commit belongs to",
        "contributor_id": "Contributor who authored this commit",
        "sha": "Full 40-character Git commit hash",
        "message": "Commit message text (truncated to 4096 chars)",
        "branch": "Branch this commit was originally made on",
        "is_merge": "Whether this is a merge commit combining two or more branches",
        "lines_added": "Total lines added across all files in this commit",
        "lines_deleted": "Total lines removed across all files in this commit",
        "files_changed": "Number of files modified in this commit",
        "authored_at": "Timestamp when the commit was originally authored",
        "committed_at": "Timestamp when the commit was applied (may differ from authored_at for rebases)",
    },
    "commit_files": {
        "id": "Auto-generated unique identifier",
        "commit_id": "Parent commit this file change belongs to",
        "file_path": "Full path of the changed file relative to repository root",
        "lines_added": "Lines added in this specific file",
        "lines_deleted": "Lines removed in this specific file",
    },
    "commit_branches": {
        "commit_id": "Commit in the association",
        "branch_id": "Branch in the association",
    },
    "pull_requests": {
        "id": "Auto-generated unique identifier",
        "repository_id": "Repository this pull request targets",
        "contributor_id": "Contributor who opened the pull request",
        "platform_pr_id": "Numeric PR/MR identifier on the hosting platform",
        "title": "Pull request title/subject line",
        "state": "Current lifecycle state: open, merged, or closed",
        "lines_added": "Total lines added across all commits in the PR",
        "lines_deleted": "Total lines removed across all commits in the PR",
        "comment_count": "Total number of review comments on the PR",
        "iteration_count": "Number of review rounds/iterations before merge",
        "created_at": "Timestamp when the PR was opened",
        "merged_at": "Timestamp when the PR was merged (null if not merged)",
        "closed_at": "Timestamp when the PR was closed without merging (null if open or merged)",
        "first_review_at": "Timestamp of the first review submitted on the PR",
    },
    "reviews": {
        "id": "Auto-generated unique identifier",
        "pull_request_id": "Pull request this review was submitted on",
        "reviewer_id": "Contributor who submitted the review",
        "state": "Review verdict: approved, changes_requested, or commented",
        "comment_count": "Number of inline comments in this review",
        "submitted_at": "Timestamp when the review was submitted",
    },
    "branches": {
        "id": "Auto-generated unique identifier",
        "repository_id": "Repository this branch belongs to",
        "name": "Full branch name (e.g. main, feature/auth)",
        "is_default": "Whether this is the repository's default branch",
        "created_at": "Timestamp when the branch was first detected",
    },
    "daily_contributor_stats": {
        "id": "Auto-generated unique identifier",
        "contributor_id": "Contributor these daily stats belong to",
        "repository_id": "Repository these daily stats are scoped to",
        "date": "Calendar date for the aggregated metrics",
        "commits": "Number of commits on this date",
        "lines_added": "Total lines added on this date",
        "lines_deleted": "Total lines removed on this date",
        "files_changed": "Number of distinct files modified on this date",
        "merges": "Number of merge commits on this date",
        "prs_opened": "Number of pull requests opened on this date",
        "prs_merged": "Number of pull requests merged on this date",
        "reviews_given": "Number of code reviews submitted on this date",
        "pr_comments": "Number of PR review comments made on this date",
    },
    "sync_jobs": {
        "id": "Auto-generated unique identifier",
        "repository_id": "Repository being synced",
        "celery_task_id": "Celery background task identifier for tracking",
        "status": "Current sync state: queued, running, completed, failed, or cancelled",
        "started_at": "Timestamp when the sync started executing",
        "finished_at": "Timestamp when the sync completed or failed",
        "error_message": "Error details if the sync failed",
        "created_at": "Timestamp when the sync job was queued",
    },
    "file_exclusion_patterns": {
        "id": "Auto-generated unique identifier",
        "pattern": "Glob pattern to match against file paths (e.g. *.lock, vendor/*)",
        "description": "Human-readable explanation of what the pattern excludes",
        "enabled": "Whether this exclusion is currently active",
        "is_default": "Whether this pattern was auto-generated from built-in defaults",
        "created_at": "Timestamp when the pattern was created",
    },
    "users": {
        "id": "Auto-generated unique identifier",
        "email": "User email address, used for login",
        "username": "Unique login username",
        "hashed_password": "Bcrypt-hashed password (never exposed via API)",
        "full_name": "Optional display name",
        "is_admin": "Whether the user has administrative privileges",
        "is_active": "Whether the account is enabled for login",
        "created_at": "Timestamp when the account was created",
    },
    "ssh_credentials": {
        "id": "Auto-generated unique identifier",
        "name": "Human-readable label for the SSH key",
        "key_type": "SSH key algorithm (ed25519 or rsa)",
        "public_key": "SSH public key in OpenSSH format",
        "private_key_encrypted": "Fernet-encrypted SSH private key",
        "fingerprint": "SSH key fingerprint for identification",
        "created_by_id": "User who generated this SSH key",
        "created_at": "Timestamp when the key was generated",
    },
    "platform_credentials": {
        "id": "Auto-generated unique identifier",
        "name": "Human-readable label for the credential",
        "platform": "Target platform (github, gitlab, azure)",
        "token_encrypted": "Fernet-encrypted API access token",
        "base_url": "Custom API base URL for self-hosted instances",
        "created_by_id": "User who created this credential",
        "created_at": "Timestamp when the credential was created",
    },
    "ai_settings": {
        "id": "Fixed singleton row identifier",
        "enabled": "Master toggle for all AI features",
        "updated_at": "Timestamp of the last settings change",
    },
    "llm_providers": {
        "id": "Auto-generated unique identifier",
        "name": "Display name for the provider configuration",
        "provider_type": "LLM provider backend (e.g. openai, anthropic, azure)",
        "model": "Model identifier (e.g. gpt-4o, claude-3-sonnet)",
        "api_key_encrypted": "Fernet-encrypted API key",
        "base_url": "Custom API endpoint for proxies or self-hosted models",
        "temperature": "Sampling temperature (0.0 = deterministic, 1.0 = creative)",
        "context_window": "Maximum token capacity of the model (null = auto-detect via LiteLLM)",
        "is_default": "Fallback provider when an agent has none assigned",
        "created_at": "Timestamp when the provider was configured",
        "updated_at": "Timestamp of the last modification",
    },
    "agents": {
        "id": "Auto-generated unique identifier",
        "slug": "URL-safe unique identifier (e.g. contribution-analyst)",
        "name": "Display name shown in the UI",
        "description": "Explains the agent's purpose and capabilities",
        "llm_provider_id": "LLM provider used for inference",
        "system_prompt": "Instructions and context injected at the start of every conversation",
        "max_iterations": "Maximum tool-calling rounds before the agent must respond",
        "summary_token_limit": "Maximum tokens for conversation summary (null = auto-detect)",
        "enabled": "Whether the agent is available for use",
        "is_builtin": "Whether this agent was auto-seeded and should not be deleted",
        "created_at": "Timestamp when the agent was created",
        "updated_at": "Timestamp of the last modification",
    },
    "agent_tool_assignments": {
        "agent_id": "Agent this tool is assigned to",
        "tool_slug": "Unique identifier of the assigned tool",
    },
    "knowledge_graphs": {
        "id": "Auto-generated unique identifier",
        "name": "Display name for the knowledge graph",
        "description": "Optional explanation of what the knowledge graph covers",
        "generation_mode": "How the graph was generated: schema_only, entities_only, schema_and_entities, or manual",
        "content": "Markdown text injected into agent system prompts as data context",
        "graph_data": "JSONB with nodes (entities) and edges (relationships) for visualization",
        "excluded_entities": "Table names excluded from the graph",
        "created_at": "Timestamp when the knowledge graph was created",
        "updated_at": "Timestamp of the last modification",
    },
    "agent_knowledge_graph_assignments": {
        "agent_id": "Agent this knowledge graph is assigned to",
        "knowledge_graph_id": "Knowledge graph providing context to the agent",
    },
    "chat_sessions": {
        "id": "Auto-generated unique identifier",
        "user_id": "User who owns this conversation",
        "agent_id": "Agent assigned to this conversation",
        "title": "Conversation title shown in the sidebar",
        "created_at": "Timestamp when the conversation started",
        "updated_at": "Timestamp of the latest activity",
        "archived_at": "Timestamp when the conversation was archived (null = active)",
        "context_summary": "Rolling structured summary of earlier messages for token management",
    },
    "chat_messages": {
        "id": "Auto-generated unique identifier",
        "session_id": "Conversation this message belongs to",
        "role": "Message author role: user, assistant, or tool",
        "content": "Full message text",
        "created_at": "Timestamp when the message was sent",
    },
}


def upgrade() -> None:
    for table, columns in COLUMN_COMMENTS.items():
        for column, comment in columns.items():
            escaped = comment.replace("'", "''")
            op.execute(f"COMMENT ON COLUMN {table}.{column} IS '{escaped}'")


def downgrade() -> None:
    for table, columns in COLUMN_COMMENTS.items():
        for column in columns:
            op.execute(f"COMMENT ON COLUMN {table}.{column} IS NULL")
