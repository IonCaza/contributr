"""Agentic contributor insight enhancer — multi-turn tool-calling loop for deep root cause analysis."""
from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.registry import is_ai_enabled, get_agent_by_slug
from app.agents.llm.manager import build_llm_from_provider
from app.agents.tools.registry import build_tools_for_slugs, build_all_tools
from app.db.models.llm_provider import LlmProvider
from app.services.insights.types import RawFinding

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

logger = logging.getLogger(__name__)

AGENT_SLUG = "contributor-coach"


def _build_investigation_prompt(raw_findings: list[RawFinding], contributor_id: uuid.UUID) -> str:
    """Compose the user-facing message sent to the agent for investigation."""
    findings_payload = [
        {
            "slug": f.slug,
            "category": f.category,
            "severity": f.severity,
            "title": f.title,
            "description": f.description,
            "recommendation": f.recommendation,
            "metric_data": f.metric_data,
        }
        for f in raw_findings
    ]

    return (
        f"## Contributor Insight Investigation\n\n"
        f"Contributor ID: `{contributor_id}`\n\n"
        f"Below are {len(raw_findings)} raw findings from deterministic analyzers. "
        f"Your job is to **investigate each finding** using the tools available to you:\n\n"
        f"1. Look up the contributor's profile, work patterns, PR summary, and cross-repo activity.\n"
        f"2. For collaboration findings, examine the review network and reviewer leaderboard.\n"
        f"3. For delivery findings, check cycle time stats, WIP analysis, and sprint overviews.\n"
        f"4. For code quality findings, examine file ownership, code hotspots, and contribution trends.\n"
        f"5. Cross-reference findings to identify root causes (e.g., 'large PRs' + 'slow first review' "
        f"+ 'high iterations' may all stem from insufficient upfront design).\n\n"
        f"After investigating, return a JSON array where each element has:\n"
        f"- `slug`: the finding's slug\n"
        f"- `description`: your enhanced description with specific data points from your investigation\n"
        f"- `recommendation`: actionable coaching advice with measurable goals\n\n"
        f"Wrap the JSON in a ```json code block.\n\n"
        f"## Raw Findings\n\n"
        f"```json\n{json.dumps(findings_payload, indent=2)}\n```"
    )


async def enhance_contributor_findings(
    db: AsyncSession,
    contributor_id: uuid.UUID,
    raw_findings: list[RawFinding],
    slog=None,
) -> list[RawFinding]:
    """Run the contributor-coach agent with tools to deeply investigate and enhance findings."""
    if not raw_findings:
        return raw_findings

    if not await is_ai_enabled(db):
        logger.info("AI disabled — skipping agentic enhancement")
        if slog:
            slog.info("enhance", "AI disabled — skipping enhancement")
        return raw_findings

    agent_config = await get_agent_by_slug(db, AGENT_SLUG)
    if not agent_config:
        logger.info("contributor-coach agent not found — falling back to raw findings")
        if slog:
            slog.info("enhance", "Contributor-coach agent not configured — skipping")
        return raw_findings

    provider: LlmProvider | None = agent_config.llm_provider
    if not provider:
        result = await db.execute(
            select(LlmProvider).where(LlmProvider.is_default.is_(True)).limit(1)
        )
        provider = result.scalar_one_or_none()
    if not provider:
        result = await db.execute(select(LlmProvider).limit(1))
        provider = result.scalar_one_or_none()
    if not provider:
        logger.warning("No LLM provider available for enhancement")
        if slog:
            slog.warning("enhance", "No LLM provider — skipping enhancement")
        return raw_findings

    if slog:
        slog.info(
            "enhance",
            f"Starting agentic investigation of {len(raw_findings)} findings "
            f"with {provider.model} (max {agent_config.max_iterations} iterations)...",
        )

    tool_slugs = {a.tool_slug for a in agent_config.tool_assignments}
    if tool_slugs:
        tools = build_tools_for_slugs(db, tool_slugs)
    else:
        tools = build_all_tools(db)

    llm = build_llm_from_provider(provider, streaming=False)

    system_prompt = agent_config.system_prompt or ""
    kg_blocks: list[str] = []
    for assignment in getattr(agent_config, "knowledge_graph_assignments", []):
        kg = getattr(assignment, "knowledge_graph", None)
        if kg and kg.content:
            kg_blocks.append(kg.content)
    if kg_blocks:
        system_prompt += "\n\n## Data Context\n\n" + "\n\n---\n\n".join(kg_blocks)

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=False,
        handle_parsing_errors=True,
        max_iterations=agent_config.max_iterations,
    )

    user_message = _build_investigation_prompt(raw_findings, contributor_id)

    try:
        result = await executor.ainvoke({"input": user_message, "chat_history": []})
        output = result.get("output", "")

        json_str = output
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]

        enhancements = json.loads(json_str.strip())

        slug_map = {e["slug"]: e for e in enhancements if isinstance(e, dict) and "slug" in e}

        enhanced_count = 0
        for f in raw_findings:
            if f.slug in slug_map:
                enhanced = slug_map[f.slug]
                if "description" in enhanced and enhanced["description"]:
                    f.description = enhanced["description"]
                if "recommendation" in enhanced and enhanced["recommendation"]:
                    f.recommendation = enhanced["recommendation"]
                enhanced_count += 1

        logger.info(
            "Agentic enhancement: enhanced %d of %d findings (used %d tool calls)",
            enhanced_count, len(raw_findings),
            len(result.get("intermediate_steps", [])),
        )
        if slog:
            tool_calls = len(result.get("intermediate_steps", []))
            slog.info(
                "enhance",
                f"Agent enhanced {enhanced_count}/{len(raw_findings)} findings "
                f"using {tool_calls} tool calls",
            )

    except Exception:
        logger.warning("Agentic enhancement failed — using raw findings", exc_info=True)
        if slog:
            slog.warning("enhance", "Agentic enhancement failed — using raw findings")

    return raw_findings
