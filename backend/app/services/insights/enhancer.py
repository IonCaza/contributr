"""AI enhancement layer — enrich raw findings via the insights-analyst agent."""
from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.registry import is_ai_enabled, get_agent_by_slug
from app.agents.llm.manager import build_llm_from_provider
from app.db.models.llm_provider import LlmProvider
from app.services.insights.types import RawFinding

logger = logging.getLogger(__name__)

AGENT_SLUG = "insights-analyst"


async def enhance_findings(
    db: AsyncSession,
    project_id: uuid.UUID | None,
    raw_findings: list[RawFinding],
    slog=None,
) -> list[RawFinding]:
    """Attempt to enrich findings via LLM. Returns findings (enhanced or original)."""
    if not raw_findings:
        return raw_findings

    if not await is_ai_enabled(db):
        logger.info("AI disabled — skipping enhancement")
        if slog:
            slog.info("enhance", "AI disabled — skipping enhancement")
        return raw_findings

    agent_config = await get_agent_by_slug(db, AGENT_SLUG)
    if not agent_config:
        logger.info("Insights-analyst agent not found — skipping enhancement")
        if slog:
            slog.info("enhance", "Insights-analyst agent not configured — skipping")
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
            slog.warning("enhance", "No LLM provider available — skipping")
        return raw_findings

    if slog:
        slog.info("enhance", f"Sending {len(raw_findings)} findings to {provider.model} for enrichment...")

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

    prompt = (
        f"{agent_config.system_prompt}\n\n"
        f"## Findings to Enhance\n\n"
        f"```json\n{json.dumps(findings_payload, indent=2)}\n```\n\n"
        f"Please return a JSON array with enhanced descriptions and recommendations."
    )

    try:
        llm = build_llm_from_provider(provider, streaming=False)
        response = await llm.ainvoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        # Extract JSON from the response (may be wrapped in markdown code block)
        json_str = content
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]

        enhancements = json.loads(json_str.strip())

        slug_map = {e["slug"]: e for e in enhancements if isinstance(e, dict) and "slug" in e}

        for f in raw_findings:
            if f.slug in slug_map:
                enhanced = slug_map[f.slug]
                if "description" in enhanced and enhanced["description"]:
                    f.description = enhanced["description"]
                if "recommendation" in enhanced and enhanced["recommendation"]:
                    f.recommendation = enhanced["recommendation"]

        logger.info("Enhanced %d of %d findings via AI", len(slug_map), len(raw_findings))
        if slog:
            slog.info("enhance", f"Enhanced {len(slug_map)} of {len(raw_findings)} findings via AI")

    except Exception:
        logger.warning("AI enhancement failed — using raw findings", exc_info=True)
        if slog:
            slog.warning("enhance", "AI enhancement failed — using raw findings")

    return raw_findings
