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
from app.db.models.auth_settings import AuthSettings, SINGLETON_ID as AUTH_SETTINGS_ID
from app.db.models.smtp_settings import SmtpSettings, SINGLETON_ID as SMTP_SETTINGS_ID
from app.db.models.email_template import EmailTemplate
from app.db.models.llm_provider import LlmProvider
from app.agents.llm.manager import build_embeddings_from_provider, get_embedding_dims
from app.agents.memory.pool import init_memory_pool, close_memory_pool
from app.api import (
    auth, projects, repositories, contributors, stats,
    ssh_keys, commits, backup, chat, ai_settings,
    file_exclusions, platform_credentials,
    llm_providers, agents, ai_tools, knowledge_graphs,
    teams as teams_api, delivery as delivery_api,
    delivery_settings as delivery_settings_api,
    team_analytics as team_analytics_api,
    custom_fields as custom_fields_api,
    insights as insights_api,
    contributor_insights as contributor_insights_api,
    team_insights as team_insights_api,
    sast as sast_api,
    dependencies as dep_api,
    feedback as feedback_api,
    mfa as mfa_api,
    smtp_settings as smtp_settings_api,
    email_templates as email_templates_api,
    auth_settings as auth_settings_api,
    oidc_providers as oidc_providers_api,
    oidc_auth as oidc_auth_api,
    pull_requests as pull_requests_api,
    adrs as adrs_api,
    project_schedules as project_schedules_api,
    presentations as presentations_api,
    project_members as project_members_api,
    access_policies as access_policies_api,
    audit as audit_api,
    webhooks as webhooks_api,
    code_reviews as code_reviews_api,
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
                    max_iterations=spec.max_iterations,
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
                if agent.system_prompt != spec.system_prompt:
                    agent.system_prompt = spec.system_prompt
                    changed = True
                if agent.max_iterations != spec.max_iterations:
                    agent.max_iterations = spec.max_iterations
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
                    max_iterations=spec.max_iterations,
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
                if agent.system_prompt != spec.system_prompt:
                    agent.system_prompt = spec.system_prompt
                    changed = True
                if agent.max_iterations != spec.max_iterations:
                    agent.max_iterations = spec.max_iterations
                    changed = True
                existing_slugs = {a.tool_slug for a in agent.tool_assignments}
                desired_slugs = set(spec.tool_slugs)
                for slug in desired_slugs - existing_slugs:
                    db.add(AgentToolAssignment(agent_id=agent.id, tool_slug=slug))
                    changed = True
                for assignment in list(agent.tool_assignments):
                    if assignment.tool_slug not in desired_slugs:
                        await db.delete(assignment)
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


async def _ensure_auth_settings():
    """Ensure the AuthSettings singleton row exists."""
    async with async_session() as db:
        result = await db.execute(select(AuthSettings).where(AuthSettings.id == AUTH_SETTINGS_ID))
        if not result.scalar_one_or_none():
            db.add(AuthSettings(id=AUTH_SETTINGS_ID))
            await db.commit()


async def _ensure_smtp_settings():
    """Ensure the SmtpSettings singleton row exists."""
    async with async_session() as db:
        result = await db.execute(select(SmtpSettings).where(SmtpSettings.id == SMTP_SETTINGS_ID))
        if not result.scalar_one_or_none():
            db.add(SmtpSettings(id=SMTP_SETTINGS_ID))
            await db.commit()


_BUILTIN_EMAIL_TEMPLATES = [
    {
        "slug": "otp_code",
        "name": "OTP Verification Code",
        "subject": "Your Contributr verification code",
        "body_html": (
            '<div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:24px">'
            '<h2 style="margin:0 0 16px">Verification Code</h2>'
            "<p>Hi {{ username }},</p>"
            '<p>Your one-time verification code is:</p>'
            '<div style="font-size:32px;font-weight:700;letter-spacing:6px;text-align:center;'
            'padding:16px;margin:16px 0;background:#f4f4f5;border-radius:8px">{{ code }}</div>'
            '<p style="color:#71717a;font-size:14px">This code expires in 5 minutes. '
            "If you did not request this, you can safely ignore this email.</p>"
            "</div>"
        ),
        "body_text": "Hi {{ username }},\n\nYour verification code is: {{ code }}\n\nThis code expires in 5 minutes.",
        "variables": {
            "code": {"description": "6-digit OTP code", "sample": "482916"},
            "username": {"description": "User's display name", "sample": "johndoe"},
        },
    },
    {
        "slug": "user_invite",
        "name": "User Invite",
        "subject": "You've been invited to Contributr",
        "body_html": (
            '<div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:24px">'
            '<h2 style="margin:0 0 16px">Welcome to Contributr</h2>'
            "<p>Hi {{ username }},</p>"
            "<p>An account has been created for you. Here are your login details:</p>"
            '<div style="background:#f4f4f5;border-radius:8px;padding:16px;margin:16px 0">'
            '<p style="margin:0 0 8px"><strong>Username:</strong> {{ username }}</p>'
            '<p style="margin:0 0 8px"><strong>Email:</strong> {{ email }}</p>'
            '<p style="margin:0"><strong>Temporary Password:</strong> {{ password }}</p>'
            "</div>"
            '<p>Please sign in and change your password immediately:</p>'
            '<p><a href="{{ login_url }}" style="display:inline-block;padding:10px 20px;'
            "background:#18181b;color:#fff;text-decoration:none;border-radius:6px;"
            'font-weight:600">Sign in to Contributr</a></p>'
            '<p style="color:#71717a;font-size:14px">If you did not expect this invitation, '
            "you can safely ignore this email.</p>"
            "</div>"
        ),
        "body_text": (
            "Hi {{ username }},\n\n"
            "An account has been created for you on Contributr.\n\n"
            "Username: {{ username }}\n"
            "Email: {{ email }}\n"
            "Temporary Password: {{ password }}\n\n"
            "Sign in at: {{ login_url }}\n\n"
            "Please change your password immediately after signing in."
        ),
        "variables": {
            "username": {"description": "User's login username", "sample": "janedoe"},
            "email": {"description": "User's email address", "sample": "jane@example.com"},
            "password": {"description": "Temporary password", "sample": "TempPass123!"},
            "login_url": {"description": "URL to the login page", "sample": "https://contributr.example.com/login"},
        },
    },
]


async def _seed_email_templates():
    """Create builtin email templates if they don't already exist."""
    async with async_session() as db:
        for spec in _BUILTIN_EMAIL_TEMPLATES:
            result = await db.execute(
                select(EmailTemplate).where(EmailTemplate.slug == spec["slug"])
            )
            if not result.scalar_one_or_none():
                db.add(EmailTemplate(is_builtin=True, **spec))
                logger.info("Seeded builtin email template: %s", spec["slug"])
        await db.commit()


async def _seed_builtin_skills():
    """Seed builtin skills into the database."""
    async with async_session() as db:
        from app.agents.skills import seed_builtin_skills
        await seed_builtin_skills(db)


async def _init_memory():
    """Start the LangGraph memory pool with an optional embedding provider.

    Reads memory_enabled and memory_embedding_provider_id from AiSettings
    to decide whether to activate the vector store.
    """
    embed_fn = None
    embed_dims = 1536
    try:
        async with async_session() as db:
            ai_row = (await db.execute(
                select(AiSettings).where(AiSettings.id == SINGLETON_ID)
            )).scalar_one_or_none()

            if ai_row and not ai_row.memory_enabled:
                logger.info("Memory disabled in AI settings — vector store skipped")
                await init_memory_pool(embed_fn=None, embed_dims=embed_dims)
                return

            provider_query = select(LlmProvider).where(LlmProvider.model_type == "embedding")
            if ai_row and ai_row.memory_embedding_provider_id:
                provider_query = provider_query.where(LlmProvider.id == ai_row.memory_embedding_provider_id)
            provider_query = provider_query.limit(1)

            row = (await db.execute(provider_query)).scalar_one_or_none()
            if row:
                model_dims = get_embedding_dims(row)

                existing_dims = None
                try:
                    from sqlalchemy import text
                    dim_row = await db.execute(text(
                        "SELECT atttypmod FROM pg_attribute "
                        "WHERE attrelid = 'store_vectors'::regclass "
                        "AND attname = 'embedding'"
                    ))
                    val = dim_row.scalar_one_or_none()
                    if val and isinstance(val, int) and val > 0:
                        existing_dims = val
                except Exception:
                    pass

                if existing_dims and existing_dims != model_dims:
                    logger.warning(
                        "store_vectors has %d-dim vectors but %s produces %d "
                        "— truncating embeddings to %d to match existing data",
                        existing_dims, row.model, model_dims, existing_dims,
                    )
                    embed_dims = existing_dims
                else:
                    embed_dims = model_dims

                embed_fn = build_embeddings_from_provider(row, dims=embed_dims)
                logger.info("Embedding provider: %s (dims=%d)", row.model, embed_dims)
            else:
                logger.info("No embedding provider configured — long-term memory store disabled")
    except Exception:
        logger.exception("Failed to resolve embedding provider")
    await init_memory_pool(embed_fn=embed_fn, embed_dims=embed_dims)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _backfill_platform_fields()
    await _ensure_ai_settings()
    await _ensure_auth_settings()
    await _ensure_smtp_settings()
    await _seed_email_templates()
    await _seed_builtin_agents()
    await _seed_builtin_skills()
    await _init_memory()

    from app.agents.context.resolver import register_entitlement_resolver
    from app.rbac.resolver import ContributrResolver
    register_entitlement_resolver(ContributrResolver())

    yield
    await close_memory_pool()
    await engine.dispose()


app = FastAPI(title="Contributr", version="0.1.0", lifespan=lifespan, redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(project_members_api.router, prefix="/api")
app.include_router(access_policies_api.router)
app.include_router(audit_api.router)
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
app.include_router(delivery_settings_api.router)
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
app.include_router(dep_api.repo_router)
app.include_router(dep_api.project_router)
app.include_router(dep_api.settings_router)
app.include_router(feedback_api.router)
app.include_router(mfa_api.router, prefix="/api")
app.include_router(smtp_settings_api.router, prefix="/api")
app.include_router(email_templates_api.router, prefix="/api")
app.include_router(auth_settings_api.router, prefix="/api")
app.include_router(oidc_providers_api.router, prefix="/api")
app.include_router(oidc_auth_api.router, prefix="/api")
app.include_router(pull_requests_api.router, prefix="/api")
app.include_router(adrs_api.router, prefix="/api")
app.include_router(project_schedules_api.router)
app.include_router(presentations_api.router, prefix="/api")
app.include_router(webhooks_api.router)
app.include_router(code_reviews_api.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
