import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import settings
from app.db.base import engine, async_session
from app.db.models import Repository
from app.db.models.agent_config import AgentConfig, AgentToolAssignment, SupervisorMember
from app.db.models.ai_settings import AiSettings, SINGLETON_ID
from app.api import (
    auth, projects, repositories, contributors, stats,
    ssh_keys, commits, backup, chat, ai_settings,
    file_exclusions, platform_credentials,
    llm_providers, agents, ai_tools, knowledge_graphs,
    teams as teams_api, delivery as delivery_api,
    team_analytics as team_analytics_api,
    custom_fields as custom_fields_api,
    insights as insights_api,
    contributor_insights as contributor_insights_api,
    team_insights as team_insights_api,
    sast as sast_api,
    feedback as feedback_api,
)
from app.api.repositories import _parse_platform_fields
from app.agents.builtin import get_builtin_agents

logger = logging.getLogger(__name__)


async def _backfill_platform_fields():
    async with async_session() as db:
        result = await db.execute(
            select(Repository).where(
                (Repository.platform_owner.is_(None)) | (Repository.platform_owner == "")
            )
        )
        repos = result.scalars().all()
        updated = 0
        for repo in repos:
            owner, name = _parse_platform_fields(repo.ssh_url, repo.clone_url, repo.platform)
            if owner and name:
                repo.platform_owner = owner
                repo.platform_repo = name
                updated += 1
        if updated:
            await db.commit()
            logger.info("Backfilled platform_owner/platform_repo for %d repositories", updated)


async def _ensure_ai_settings():
    """Ensure the AiSettings singleton row exists."""
    async with async_session() as db:
        result = await db.execute(select(AiSettings).where(AiSettings.id == SINGLETON_ID))
        if not result.scalar_one_or_none():
            db.add(AiSettings(id=SINGLETON_ID, enabled=False))
            await db.commit()


async def _seed_builtin_agents():
    """Ensure all builtin agent definitions exist.

    Fresh DB: creates agents with full spec (prompt, tools, description).
    Existing DB: respects user customizations -- only fills in a blank system
    prompt and adds new tool assignments.

    Supervisor agents are processed last so their member references resolve.
    """
    async with async_session() as db:
        changed = False
        supervisor_specs: list = []

        for spec in get_builtin_agents():
            if getattr(spec, "agent_type", "standard") == "supervisor":
                supervisor_specs.append(spec)
                continue

            result = await db.execute(
                select(AgentConfig).where(AgentConfig.slug == spec.slug)
            )
            agent = result.scalar_one_or_none()
            if agent is None:
                agent = AgentConfig(
                    slug=spec.slug,
                    name=spec.name,
                    description=spec.description,
                    system_prompt=spec.system_prompt,
                    is_builtin=True,
                    enabled=True,
                )
                db.add(agent)
                await db.flush()
                for tool_slug in spec.tool_slugs:
                    db.add(AgentToolAssignment(agent_id=agent.id, tool_slug=tool_slug))
                changed = True
                logger.info("Seeded builtin agent: %s", spec.slug)
            else:
                if not agent.system_prompt or agent.system_prompt == "":
                    agent.system_prompt = spec.system_prompt
                    changed = True
                existing_slugs = {a.tool_slug for a in agent.tool_assignments}
                for slug in set(spec.tool_slugs) - existing_slugs:
                    db.add(AgentToolAssignment(agent_id=agent.id, tool_slug=slug))
                    changed = True

        if changed:
            await db.flush()

        for spec in supervisor_specs:
            result = await db.execute(
                select(AgentConfig).where(AgentConfig.slug == spec.slug)
            )
            agent = result.scalar_one_or_none()
            if agent is None:
                agent = AgentConfig(
                    slug=spec.slug,
                    name=spec.name,
                    description=spec.description,
                    system_prompt=spec.system_prompt,
                    agent_type="supervisor",
                    is_builtin=True,
                    enabled=True,
                )
                db.add(agent)
                await db.flush()
                for tool_slug in spec.tool_slugs:
                    db.add(AgentToolAssignment(agent_id=agent.id, tool_slug=tool_slug))
                for member_slug in getattr(spec, "member_slugs", []):
                    member_row = (await db.execute(
                        select(AgentConfig).where(AgentConfig.slug == member_slug)
                    )).scalar_one_or_none()
                    if member_row:
                        db.add(SupervisorMember(
                            supervisor_id=agent.id,
                            member_agent_id=member_row.id,
                        ))
                changed = True
                logger.info("Seeded builtin supervisor: %s", spec.slug)
            else:
                if agent.agent_type != "supervisor":
                    agent.agent_type = "supervisor"
                    changed = True
                if not agent.system_prompt or agent.system_prompt == "":
                    agent.system_prompt = spec.system_prompt
                    changed = True
                existing_member_ids = {
                    r.member_agent_id for r in (await db.execute(
                        select(SupervisorMember)
                        .where(SupervisorMember.supervisor_id == agent.id)
                    )).scalars().all()
                }
                for member_slug in getattr(spec, "member_slugs", []):
                    member_row = (await db.execute(
                        select(AgentConfig).where(AgentConfig.slug == member_slug)
                    )).scalar_one_or_none()
                    if member_row and member_row.id not in existing_member_ids:
                        db.add(SupervisorMember(
                            supervisor_id=agent.id,
                            member_agent_id=member_row.id,
                        ))
                        changed = True

        if changed:
            await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _backfill_platform_fields()
    await _ensure_ai_settings()
    await _seed_builtin_agents()
    yield
    await engine.dispose()


app = FastAPI(title="Contributr", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(repositories.router, prefix="/api")
app.include_router(contributors.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(ssh_keys.router, prefix="/api")
app.include_router(commits.router, prefix="/api")
app.include_router(backup.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(ai_settings.router, prefix="/api")
app.include_router(llm_providers.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(ai_tools.router, prefix="/api")
app.include_router(knowledge_graphs.router, prefix="/api")
app.include_router(file_exclusions.router, prefix="/api")
app.include_router(platform_credentials.router, prefix="/api")
app.include_router(teams_api.router)
app.include_router(delivery_api.router)
app.include_router(team_analytics_api.router)
app.include_router(custom_fields_api.router)
app.include_router(insights_api.router)
app.include_router(contributor_insights_api.router)
app.include_router(team_insights_api.router)
app.include_router(sast_api.repo_router)
app.include_router(sast_api.project_router)
app.include_router(sast_api.profile_router)
app.include_router(sast_api.settings_router)
app.include_router(sast_api.ignored_router)
app.include_router(feedback_api.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
