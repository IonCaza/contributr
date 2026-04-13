"""Agent tools for managing Architecture Decision Records."""

from __future__ import annotations

import logging
import os
import re
import subprocess
from datetime import datetime, timezone

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.base import async_session as _session_factory
from app.db.models.adr import Adr, AdrRepository, AdrTemplate, AdrStatus
from app.db.models import Project
from app.db.models.repository import Repository
from app.db.models.pull_request import PullRequest
from app.db.models.pr_comment import PRComment
from app.agents.tools.base import ToolDefinition
from app.agents.tools.registry import register_tool_category

logger = logging.getLogger(__name__)

CATEGORY = "adr_management"

DEFINITIONS = [
    ToolDefinition("list_adrs", "List ADRs", "List all Architecture Decision Records in a project", CATEGORY, concurrency_safe=True),
    ToolDefinition("read_adr", "Read ADR", "Read the full content of a specific ADR", CATEGORY, concurrency_safe=True),
    ToolDefinition("create_adr", "Create ADR", "Create a new Architecture Decision Record", CATEGORY),
    ToolDefinition("update_adr", "Update ADR", "Update an existing ADR's content or title", CATEGORY),
    ToolDefinition("generate_adr_from_text", "Generate ADR from Text", "Convert freeform text into a structured ADR using a template", CATEGORY),
    ToolDefinition("suggest_adr", "Suggest ADR", "Analyze a topic and suggest whether an ADR is needed, with a draft outline", CATEGORY, concurrency_safe=True),
    ToolDefinition("analyze_pr_for_adrs", "Analyze PR for ADRs", "Analyze a pull request's review comments and code changes to identify architectural decisions worth documenting as ADRs", CATEGORY, concurrency_safe=True),
]

SNIPPET_RADIUS = 15
MAX_SNIPPET_BYTES = 4000


async def get_adr_llm_provider(db: AsyncSession):
    """Resolve the LLM provider for ADR operations.

    Prefers the ADR Architect agent's configured provider, falls back to the
    global default chat provider.
    """
    from app.db.models.agent_config import AgentConfig
    from app.db.models.llm_provider import LlmProvider

    result = await db.execute(
        select(AgentConfig).where(AgentConfig.slug == "adr-architect").limit(1)
    )
    agent = result.scalar_one_or_none()
    if agent and agent.llm_provider_id:
        prov = await db.execute(select(LlmProvider).where(LlmProvider.id == agent.llm_provider_id))
        provider = prov.scalar_one_or_none()
        if provider:
            return provider

    result = await db.execute(
        select(LlmProvider).where(LlmProvider.is_default.is_(True), LlmProvider.model_type == "chat").limit(1)
    )
    return result.scalar_one_or_none()


async def _find_project_id(db: AsyncSession, name: str):
    result = await db.execute(
        select(Project).where(Project.name.ilike(f"%{name}%")).limit(1)
    )
    project = result.scalar_one_or_none()
    return project.id if project else None


def _build_adr_tools(db: AsyncSession) -> list:

    @tool
    async def list_adrs(project_name: str, status: str = "") -> str:
        """List all Architecture Decision Records in a project.

        Args:
            project_name: Project name (fuzzy match).
            status: Optional status filter (proposed, accepted, deprecated, superseded, rejected).
        """
        async with _session_factory() as s:
            project_id = await _find_project_id(s, project_name)
            if not project_id:
                return f"No project found matching '{project_name}'."

            q = select(Adr).where(Adr.project_id == project_id)
            if status:
                try:
                    q = q.where(Adr.status == AdrStatus(status))
                except ValueError:
                    pass
            q = q.order_by(Adr.adr_number)

            result = await s.execute(q)
            adrs = result.scalars().all()

        if not adrs:
            return f"No ADRs found in project '{project_name}'."

        header = f"**{project_name}** — {len(adrs)} ADR(s)\n\n"
        rows = []
        for a in adrs:
            rows.append(f"- **ADR-{a.adr_number}**: {a.title} [{a.status.value}]")
        return header + "\n".join(rows)

    @tool
    async def read_adr(project_name: str, adr_number: int) -> str:
        """Read the full content of a specific ADR.

        Args:
            project_name: Project name (fuzzy match).
            adr_number: The ADR number to read.
        """
        async with _session_factory() as s:
            project_id = await _find_project_id(s, project_name)
            if not project_id:
                return f"No project found matching '{project_name}'."

            result = await s.execute(
                select(Adr).where(Adr.project_id == project_id, Adr.adr_number == adr_number).limit(1)
            )
            adr = result.scalar_one_or_none()
            if not adr:
                return f"ADR-{adr_number} not found in project '{project_name}'."

            header = (
                f"**ADR-{adr.adr_number}: {adr.title}**\n"
                f"Status: {adr.status.value} | Created: {adr.created_at.strftime('%Y-%m-%d')}\n"
                f"{'Superseded by: ' + str(adr.superseded_by_id) if adr.superseded_by_id else ''}\n\n"
            )
            return header + adr.content

    @tool
    async def create_adr(project_name: str, title: str, content: str) -> str:
        """Create a new Architecture Decision Record. ADRs are always created in PROPOSED status.

        Args:
            project_name: Project name (fuzzy match).
            title: ADR title.
            content: Full markdown content of the ADR.
        """
        from app.db.models import User

        async with _session_factory() as s:
            project_id = await _find_project_id(s, project_name)
            if not project_id:
                return f"No project found matching '{project_name}'."

            config_result = await s.execute(
                select(AdrRepository).where(AdrRepository.project_id == project_id)
            )
            config = config_result.scalar_one_or_none()
            adr_number = config.next_number if config else 1
            if config:
                config.next_number += 1

            admin_result = await s.execute(select(User.id).limit(1))
            admin_id = admin_result.scalar()

            adr = Adr(
                project_id=project_id,
                adr_number=adr_number,
                title=title,
                slug=Adr.make_slug(title),
                status=AdrStatus.PROPOSED,
                content=content,
                created_by_id=admin_id,
            )
            s.add(adr)
            await s.commit()

        return f"Created **ADR-{adr_number}: {title}** with status 'PROPOSED'."

    @tool
    async def update_adr(project_name: str, adr_number: int, content: str = "", title: str = "") -> str:
        """Update an existing ADR's content or title. Status changes are managed by the team through the UI.

        Args:
            project_name: Project name (fuzzy match).
            adr_number: The ADR number to update.
            content: New content (empty to keep current).
            title: New title (empty to keep current).
        """
        async with _session_factory() as s:
            project_id = await _find_project_id(s, project_name)
            if not project_id:
                return f"No project found matching '{project_name}'."

            result = await s.execute(
                select(Adr).where(Adr.project_id == project_id, Adr.adr_number == adr_number).limit(1)
            )
            adr = result.scalar_one_or_none()
            if not adr:
                return f"ADR-{adr_number} not found in project '{project_name}'."

            changes = []
            if content:
                adr.content = content
                changes.append("content")
            if title:
                adr.title = title
                adr.slug = Adr.make_slug(title)
                changes.append("title")

            if not changes:
                return f"No changes provided for ADR-{adr_number}."

            adr.updated_at = datetime.now(timezone.utc)
            await s.commit()

        return f"Updated ADR-{adr_number} ({', '.join(changes)})."

    @tool
    async def generate_adr_from_text(project_name: str, text: str) -> str:
        """Convert freeform text into a structured ADR using the project's default template.

        Args:
            project_name: Project name (fuzzy match).
            text: Freeform text describing the decision context, options, and outcome.
        """
        from app.agents.llm.manager import build_llm_from_provider
        from app.db.models import User

        async with _session_factory() as s:
            project_id = await _find_project_id(s, project_name)
            if not project_id:
                return f"No project found matching '{project_name}'."

            tmpl_result = await s.execute(
                select(AdrTemplate).where(
                    ((AdrTemplate.project_id == project_id) | (AdrTemplate.project_id.is_(None)))
                    & (AdrTemplate.is_default == True)
                ).limit(1)
            )
            tmpl = tmpl_result.scalar_one_or_none()
            template_content = tmpl.content if tmpl else ""

            provider = await get_adr_llm_provider(s)
            if not provider:
                return "No LLM provider configured. Assign one to the ADR Architect agent or set a default provider."

        prompt = (
            "You are an expert software architect. Generate a well-structured ADR from the text below. "
            "Use the provided template format.\n\n"
            f"Template:\n```\n{template_content}\n```\n\n"
            f"Input:\n{text}\n\n"
            "Replace all {{...}} placeholders with content from the input. Return only the markdown ADR."
        )

        try:
            llm = build_llm_from_provider(provider, streaming=False)
            response = await llm.ainvoke(prompt)
            generated = response.content or ""
            if isinstance(generated, list):
                generated = "".join(
                    c.get("text", "") if isinstance(c, dict) else str(c) for c in generated
                )
        except Exception as e:
            return f"AI generation failed: {e}"

        title = text[:80]
        for line in generated.split("\n"):
            if line.strip().startswith("# "):
                t = line.strip()[2:].strip()
                num_prefix = re.match(r"\d+\.\s*", t)
                if num_prefix:
                    t = t[num_prefix.end():]
                title = t
                break

        async with _session_factory() as s:
            config_result = await s.execute(
                select(AdrRepository).where(AdrRepository.project_id == project_id)
            )
            config = config_result.scalar_one_or_none()
            adr_number = config.next_number if config else 1
            if config:
                config.next_number += 1

            admin_result = await s.execute(select(User.id).limit(1))
            admin_id = admin_result.scalar()

            adr = Adr(
                project_id=project_id,
                adr_number=adr_number,
                title=title,
                slug=Adr.make_slug(title),
                content=generated,
                created_by_id=admin_id,
            )
            s.add(adr)
            await s.commit()

        return f"Generated and created **ADR-{adr_number}: {title}**.\n\n{generated[:500]}..."

    @tool
    async def suggest_adr(topic: str, project_name: str = "") -> str:
        """Analyze a topic and suggest whether an ADR is needed, providing a draft outline.

        Args:
            topic: The architectural topic or decision to analyze.
            project_name: Optional project name for context.
        """
        from app.agents.llm.manager import build_llm_from_provider

        async with _session_factory() as s:
            provider = await get_adr_llm_provider(s)
            if not provider:
                return "No LLM provider configured. Assign one to the ADR Architect agent or set a default provider."

        prompt = (
            "You are an expert software architect. Analyze the following topic and determine if an "
            "Architecture Decision Record (ADR) is warranted.\n\n"
            f"Topic: {topic}\n\n"
            "Respond with:\n"
            "1. **Recommendation**: Yes/No - should an ADR be created?\n"
            "2. **Reasoning**: Why or why not?\n"
            "3. **Draft Outline** (if yes): A brief outline of what the ADR would cover, including "
            "context, decision drivers, options considered, and recommended decision.\n"
            "4. **Suggested Title**: A concise ADR title."
        )

        try:
            llm = build_llm_from_provider(provider, streaming=False)
            response = await llm.ainvoke(prompt)
            content = response.content or "No response generated."
            if isinstance(content, list):
                content = "".join(
                    c.get("text", "") if isinstance(c, dict) else str(c) for c in content
                )
            return content
        except Exception as e:
            return f"AI analysis failed: {e}"

    @tool
    async def analyze_pr_for_adrs(repo_name: str, pr_number: int) -> str:
        """Analyze a pull request's review comments and surrounding code to identify architectural decisions worth documenting as ADRs.

        Fetches all review comments, pulls code snippets around file-level
        comments, and uses AI to identify and rank architectural decision
        candidates.

        Args:
            repo_name: Repository name (fuzzy match).
            pr_number: The platform PR/MR number.
        """
        from app.agents.llm.manager import build_llm_from_provider

        async with _session_factory() as s:
            result = await s.execute(
                select(Repository).where(Repository.name.ilike(f"%{repo_name}%")).limit(1)
            )
            repo = result.scalar_one_or_none()
            if not repo:
                return f"No repository found matching '{repo_name}'."

            result = await s.execute(
                select(PullRequest)
                .where(PullRequest.repository_id == repo.id, PullRequest.platform_pr_id == pr_number)
                .options(selectinload(PullRequest.comments))
            )
            pr = result.scalar_one_or_none()
            if not pr:
                return f"PR #{pr_number} not found in repository '{repo.name}'."

            comments = [c for c in pr.comments if c.body and c.body.strip()]
            if not comments:
                return f"PR #{pr_number} has no review comments to analyze."

            bare_path = os.path.join(settings.repos_cache_dir, str(repo.id))
            ref = repo.default_branch or "main"
            repo_name_display = repo.name

            blocks: list[str] = []
            for c in comments:
                block = f"### Comment by {c.author_name or 'unknown'}"
                if c.file_path:
                    block += f" on `{c.file_path}`"
                    if c.line_number:
                        block += f" (line {c.line_number})"
                block += f"\n{c.body.strip()}\n"

                if c.file_path and c.line_number and os.path.isdir(bare_path):
                    snippet = _git_snippet(bare_path, ref, c.file_path, c.line_number)
                    if snippet:
                        block += f"\n**Code context:**\n```\n{snippet}\n```\n"

                blocks.append(block)

            context_text = "\n---\n".join(blocks)

            provider = await get_adr_llm_provider(s)
            if not provider:
                return (
                    "No LLM provider configured. Assign one to the ADR Architect "
                    "agent or set a default provider."
                )

        prompt = (
            "You are an expert software architect. Analyze the following pull request "
            "review comments and their surrounding code context.\n\n"
            "Identify distinct **architectural decisions** being discussed — things like "
            "technology choices, design patterns, API contracts, data-model changes, "
            "security strategies, or cross-cutting concerns.\n\n"
            "For each candidate:\n"
            "1. **Title** — a concise ADR-style title\n"
            "2. **Summary** — 2-3 sentence description of the decision and its context\n"
            "3. **Key discussion points** — bullet list of the most relevant comment excerpts\n"
            "4. **Relevant files** — the files involved\n"
            "5. **Relevance** — HIGH / MEDIUM / LOW\n\n"
            "Group related comments into the same candidate. "
            "Return a **numbered list**. If nothing warrants an ADR, say so.\n\n"
            f"---\n\nPR #{pr_number} in {repo_name_display} — {len(comments)} comment(s)\n\n"
            f"{context_text}"
        )

        try:
            llm = build_llm_from_provider(provider, streaming=False)
            response = await llm.ainvoke(prompt)
            content = response.content or "No analysis generated."
            if isinstance(content, list):
                content = "".join(
                    c.get("text", "") if isinstance(c, dict) else str(c) for c in content
                )
            return content
        except Exception as e:
            return f"AI analysis failed: {e}"

    return [
        list_adrs, read_adr, create_adr, update_adr,
        generate_adr_from_text, suggest_adr, analyze_pr_for_adrs,
    ]


def _git_snippet(bare_path: str, ref: str, file_path: str, line: int) -> str:
    """Extract lines around *line* from a file in a bare git repo."""
    try:
        raw = subprocess.run(
            ["git", "show", f"{ref}:{file_path}"],
            cwd=bare_path, capture_output=True, text=True, timeout=10,
        )
        if raw.returncode != 0:
            return ""
        lines = raw.stdout.splitlines()
        start = max(0, line - SNIPPET_RADIUS - 1)
        end = min(len(lines), line + SNIPPET_RADIUS)
        snippet_lines = []
        for i, l in enumerate(lines[start:end], start=start + 1):
            marker = ">>>" if i == line else "   "
            snippet_lines.append(f"{marker} {i:>4} | {l}")
        snippet = "\n".join(snippet_lines)
        return snippet[:MAX_SNIPPET_BYTES]
    except Exception:
        return ""


register_tool_category(CATEGORY, DEFINITIONS, _build_adr_tools, session_safe=True)
