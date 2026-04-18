import logging
import uuid

from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool, StructuredTool
from sqlalchemy import select

from app.agents.base import build_agent
from app.agents.context import current_session_id, current_user_id
from app.agents.memory.recall import format_recalled_for_prompt, recall_relevant_memories
from app.agents.memory.session_notes import load_session_notes
from app.agents.settings_cache import get_memory_settings
from app.agents.tools.feedback_gap import build_report_capability_gap_tool
from app.db.base import async_session
from app.db.models.agent_config import AgentConfig
from app.db.models.llm_provider import LlmProvider

logger = logging.getLogger(__name__)


def _make_child_runner(member, provider):
    """Factory that returns a clean async function with only ``query: str`` in its signature.

    Each invocation creates its own database session so that a failure in
    one child agent does not poison the transaction for sibling agents.
    The child receives session notes and recalled memories so it can
    understand the ongoing conversation without its own checkpoint history.
    """

    async def _run_child(query: str) -> str:
        logger.info("Supervisor delegating to %s: %s", member.slug, query[:120])
        try:
            session_id = current_session_id.get(None)
            user_id = current_user_id.get(None)

            session_context = ""
            if session_id:
                try:
                    notes, _ = await load_session_notes(session_id)
                    if notes:
                        session_context = (
                            "\n\n<session_context>\n"
                            "The following session notes describe the current conversation "
                            "so far. Use this as your PRIMARY context for understanding "
                            "what the user is working on. Do NOT ask the user to clarify "
                            "information that is already in these notes.\n\n"
                            f"{notes}\n"
                            "</session_context>"
                        )
                except Exception:
                    logger.debug("Failed to load session notes for child agent", exc_info=True)

            recalled_context = ""
            if user_id:
                try:
                    mem_settings = await get_memory_settings()
                    if mem_settings.memory_enabled:
                        from app.agents.llm.manager import build_llm_from_provider
                        recall_llm = build_llm_from_provider(provider, streaming=False)
                        async with async_session() as recall_db:
                            recalled = await recall_relevant_memories(
                                recall_db, user_id, query, recall_llm,
                            )
                            recalled_context = format_recalled_for_prompt(recalled)
                except Exception:
                    logger.debug("Failed to recall memories for child agent", exc_info=True)

            child_extra_tools: list[BaseTool] = []
            if session_id is not None:
                child_extra_tools.append(
                    build_report_capability_gap_tool(session_id, member.slug)
                )

            async with async_session() as child_db:
                child_agent, max_iter = build_agent(
                    member, provider, child_db,
                    extra_tools=child_extra_tools or None,
                    recalled_context=recalled_context,
                )
                child_thread = str(uuid.uuid4())
                full_query = query + session_context

                result = await child_agent.ainvoke(
                    {"messages": [HumanMessage(content=full_query)]},
                    config={
                        "configurable": {"thread_id": child_thread},
                        "recursion_limit": (max_iter or 25) * 2,
                    },
                )
                last_msg = result["messages"][-1]
                response = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
                logger.info("Child agent %s responded (%d chars)", member.slug, len(response))
                return response
        except Exception as e:
            logger.exception("Child agent %s failed: %s", member.slug, e)
            return f"The {member.name} agent encountered an error: {e}"

    return _run_child


# Routing hints appended to each ask_<slug> tool description so the
# supervisor can recognise relevant questions even when the user phrases
# them ambiguously. Slugs that are not in this map fall back to the plain
# agent description from the database.
_ROUTING_HINTS: dict[str, str] = {
    "contribution-analyst": (
        "ROUTE WHEN: questions about git commits, pull requests, code reviews, "
        "contributors, repositories, branches, file churn, hotspots, ownership, "
        "review networks, or work patterns."
    ),
    "delivery-analyst": (
        "ROUTE WHEN: questions about sprints, iterations, velocity, throughput, "
        "cycle time, lead time, WIP, cumulative flow, burndown, backlog health, "
        "backlog composition, stale items, bug / quality metrics, team delivery, "
        "team capacity vs load, carry-over / sprint churn / iteration moves / "
        "rescheduled stories, feature backlog rollup, story sizing trends, the "
        "trusted-backlog scorecard, or long-running stories. This specialist "
        "owns everything sprint / iteration / work-item related — DO NOT answer "
        "such questions yourself or send them to contribution-analyst."
    ),
    "delivery-code-analyst": (
        "ROUTE WHEN: cross-domain questions linking code and delivery — commit-"
        "to-work-item linkage, commits per story point, or delivery efficiency "
        "per contributor."
    ),
    "text-to-sql": (
        "ROUTE WHEN: user asks for raw tabular output, ad-hoc SELECTs, or a "
        "specific list that doesn't map to a pre-built analytics tool."
    ),
    "insights-analyst": (
        "ROUTE WHEN: user wants automated analysis findings explained, root-"
        "caused, or summarised."
    ),
    "contributor-coach": (
        "ROUTE WHEN: coaching, habits, burnout, or craft questions about an "
        "individual contributor."
    ),
    "sast-analyst": (
        "ROUTE WHEN: static-analysis, SAST, CVE, CWE, security-scanning, or "
        "vulnerability-trend questions."
    ),
    "dependency-analyst": (
        "ROUTE WHEN: third-party dependency, SBOM, package-version, or outdated-"
        "library questions."
    ),
    "code-reviewer": (
        "ROUTE WHEN: user wants a PR review, an ADR-compliance check, or deep "
        "reading of source code / diffs."
    ),
    "verification-agent": (
        "ROUTE WHEN: you want an independent second opinion on an earlier "
        "answer before replying to the user."
    ),
}


def build_delegation_tools(
    member_configs: list[AgentConfig],
    fallback_provider: LlmProvider,
) -> list[BaseTool]:
    """Wrap each member agent as a callable LangChain tool for the supervisor.

    Each tool runs the child agent's full tool-calling loop internally
    and returns the final text response.  Each invocation creates its
    own database session so concurrent delegations don't conflict.
    """
    tools: list[BaseTool] = []

    for member in member_configs:
        if not member.enabled:
            continue

        tool_name = f"ask_{member.slug.replace('-', '_')}"
        routing_hint = _ROUTING_HINTS.get(member.slug, "")
        tool_desc = (
            f"Delegate a question to the {member.name} agent. "
            f"{member.description or ''} "
            f"{routing_hint} "
            f"IMPORTANT: Always include full context in the query — the specific "
            f"entities (PR numbers, repo names, contributor names, project name, "
            f"sprint/iteration name, team name, work-item ID, etc.), any relevant "
            f"details, and the specific question. The delegated agent cannot see "
            f"prior conversation messages."
        )
        tool_desc = " ".join(tool_desc.split())  # collapse whitespace

        runner = _make_child_runner(member, fallback_provider)

        tool = StructuredTool.from_function(
            coroutine=runner,
            name=tool_name,
            description=tool_desc,
        )
        tools.append(tool)

    return tools


def build_prompt_management_tools(
    member_configs: list[AgentConfig],
) -> list[BaseTool]:
    """Build tools that let a supervisor view and update member agent prompts.

    Hierarchy enforcement: the allowed slug set is derived from *member_configs*
    at build time, so the tools can only target agents the supervisor owns.
    """
    allowed_slugs = {m.slug for m in member_configs if m.enabled}
    slug_list = ", ".join(sorted(allowed_slugs))

    async def _view_agent_prompt(agent_slug: str) -> str:
        if agent_slug not in allowed_slugs:
            return (
                f"Error: '{agent_slug}' is not in your hierarchy. "
                f"Available agents: {slug_list}"
            )
        async with async_session() as db:
            agent = await db.scalar(
                select(AgentConfig).where(AgentConfig.slug == agent_slug)
            )
            if not agent:
                return f"Error: Agent '{agent_slug}' not found."
            prompt = agent.system_prompt or "(empty)"
            return (
                f"## System prompt for {agent.name} (`{agent.slug}`)\n"
                f"**Length**: {len(prompt)} chars\n\n"
                f"{prompt}"
            )

    async def _update_agent_prompt(agent_slug: str, new_prompt: str) -> str:
        if agent_slug not in allowed_slugs:
            return (
                f"Error: '{agent_slug}' is not in your hierarchy. "
                f"Available agents: {slug_list}"
            )
        if not new_prompt or not new_prompt.strip():
            return "Error: new_prompt cannot be empty."
        async with async_session() as db:
            agent = await db.scalar(
                select(AgentConfig).where(AgentConfig.slug == agent_slug)
            )
            if not agent:
                return f"Error: Agent '{agent_slug}' not found."
            old_len = len(agent.system_prompt or "")
            agent.system_prompt = new_prompt.strip()
            await db.commit()
            warning = ""
            if agent.is_builtin:
                warning = (
                    " Warning: this is a built-in agent whose prompt resets to "
                    "the default on application restart."
                )
            return (
                f"Updated system prompt for {agent.name} (`{agent.slug}`). "
                f"Previous: {old_len} chars → New: {len(agent.system_prompt)} chars. "
                f"Takes effect on the agent's next invocation.{warning}"
            )

    return [
        StructuredTool.from_function(
            coroutine=_view_agent_prompt,
            name="view_agent_prompt",
            description=(
                "View the current system prompt of a member agent in your "
                "hierarchy. Use this to understand how a child agent is "
                "instructed before deciding whether to update its prompt."
            ),
        ),
        StructuredTool.from_function(
            coroutine=_update_agent_prompt,
            name="update_agent_prompt",
            description=(
                "Update the system prompt of a member agent in your hierarchy. "
                "This replaces the agent's core instructions. Knowledge-graph "
                "context and behavioral directives are appended separately at "
                "runtime. Always call view_agent_prompt first."
            ),
        ),
    ]
