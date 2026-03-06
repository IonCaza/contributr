import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import settings
from app.db.base import engine, async_session
from app.db.models import Repository
from app.api import auth, projects, repositories, contributors, stats, ssh_keys, commits, backup, chat, ai_settings, file_exclusions, platform_credentials
from app.api.repositories import _parse_platform_fields

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _backfill_platform_fields()
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
app.include_router(file_exclusions.router, prefix="/api")
app.include_router(platform_credentials.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
