import json
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.base import get_db
from app.db.models import (
    User, Commit, Branch, Contributor, ContributorAlias,
    Repository, PullRequest, Review, SSHCredential, SyncJob,
    DailyContributorStats, CommitFile, FileExclusionPattern,
    PlatformCredential, AiSettings, LlmProvider,
    AgentConfig, AgentToolAssignment,
    KnowledgeGraph, AgentKnowledgeGraphAssignment,
    ChatSession, ChatMessage,
    Team, TeamMember, Iteration,
    WorkItem, WorkItemRelation, WorkItemCommit,
    DailyDeliveryStats, DeliverySyncJob, CustomFieldConfig,
    InsightRun, InsightFinding,
    ContributorInsightRun, ContributorInsightFinding,
)
from app.db.models.project import Project, project_contributors
from app.db.models.branch import commit_branches
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/backup", tags=["backup"])

DUMP_VERSION = 1
CHUNK_SIZE = 500

TABLE_MODELS = [
    # Roots (no foreign keys)
    ("users", User),
    ("contributors", Contributor),
    ("ai_settings", AiSettings),
    ("file_exclusion_patterns", FileExclusionPattern),
    ("llm_providers", LlmProvider),
    ("knowledge_graphs", KnowledgeGraph),
    # Level 1 (depend on roots)
    ("platform_credentials", PlatformCredential),
    ("ssh_credentials", SSHCredential),
    ("contributor_aliases", ContributorAlias),
    # Level 2 (depend on level 1)
    ("projects", Project),
    # Level 3 (depend on level 2)
    ("repositories", Repository),
    ("teams", Team),
    ("iterations", Iteration),
    ("custom_field_configs", CustomFieldConfig),
    ("delivery_sync_jobs", DeliverySyncJob),
    ("agents", AgentConfig),
    ("insight_runs", InsightRun),
    ("contributor_insight_runs", ContributorInsightRun),
    # Level 4 (depend on level 3)
    ("branches", Branch),
    ("commits", Commit),
    ("pull_requests", PullRequest),
    ("sync_jobs", SyncJob),
    ("daily_contributor_stats", DailyContributorStats),
    ("team_members", TeamMember),
    ("agent_tool_assignments", AgentToolAssignment),
    ("agent_knowledge_graph_assignments", AgentKnowledgeGraphAssignment),
    # Level 5 (depend on level 4)
    ("commit_files", CommitFile),
    ("reviews", Review),
    ("work_items", WorkItem),
    ("chat_sessions", ChatSession),
    ("insight_findings", InsightFinding),
    ("contributor_insight_findings", ContributorInsightFinding),
    # Level 6 (depend on level 5)
    ("work_item_relations", WorkItemRelation),
    ("work_item_commits", WorkItemCommit),
    ("daily_delivery_stats", DailyDeliveryStats),
    ("chat_messages", ChatMessage),
]

ASSOC_TABLES = [
    ("commit_branches", commit_branches),
    ("project_contributors", project_contributors),
]


def _serialize(val):
    if val is None:
        return None
    if isinstance(val, uuid.UUID):
        return str(val)
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, date):
        return val.isoformat()
    if hasattr(val, "value") and not isinstance(val, (bool, int, float, str)):
        return val.value
    return val


def _row_to_dict(row) -> dict:
    return {col.name: _serialize(getattr(row, col.name)) for col in row.__table__.columns}


def _parse_row(model, row_dict: dict) -> dict:
    parsed = {}
    for col in model.__table__.columns:
        if col.name not in row_dict:
            continue
        val = row_dict[col.name]
        if val is None:
            parsed[col.name] = None
            continue
        try:
            pt = col.type.python_type
        except NotImplementedError:
            parsed[col.name] = val
            continue
        if pt is uuid.UUID and isinstance(val, str):
            parsed[col.name] = uuid.UUID(val)
        elif pt is datetime and isinstance(val, str):
            parsed[col.name] = datetime.fromisoformat(val)
        elif pt is date and isinstance(val, str):
            parsed[col.name] = date.fromisoformat(val)
        else:
            parsed[col.name] = val
    return parsed


@router.get("/export")
async def export_backup(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    tables: dict[str, list] = {}

    for name, model in TABLE_MODELS:
        result = await db.execute(select(model))
        tables[name] = [_row_to_dict(r) for r in result.scalars().all()]

    for name, assoc in ASSOC_TABLES:
        result = await db.execute(select(assoc))
        rows = result.mappings().all()
        tables[name] = [{c.name: _serialize(row[c.name]) for c in assoc.columns} for row in rows]

    dump = {
        "version": DUMP_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "tables": tables,
    }

    return Response(
        content=json.dumps(dump, default=str),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=contributr-backup.json"},
    )


@router.post("/import")
async def import_backup(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    content = await file.read()
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")

    if data.get("version") != DUMP_VERSION:
        raise HTTPException(status_code=400, detail=f"Unsupported backup version (expected {DUMP_VERSION})")

    tables = data.get("tables", {})
    counts: dict[str, dict] = {}

    for name, model in TABLE_MODELS:
        rows = tables.get(name, [])
        if not rows:
            counts[name] = {"submitted": 0, "imported": 0}
            continue
        parsed = [_parse_row(model, r) for r in rows]
        imported = 0
        for i in range(0, len(parsed), CHUNK_SIZE):
            chunk = parsed[i : i + CHUNK_SIZE]
            stmt = pg_insert(model).values(chunk).on_conflict_do_nothing()
            result = await db.execute(stmt)
            imported += result.rowcount
        counts[name] = {"submitted": len(rows), "imported": imported}

    for name, assoc in ASSOC_TABLES:
        rows = tables.get(name, [])
        if not rows:
            counts[name] = {"submitted": 0, "imported": 0}
            continue
        parsed = [{k: uuid.UUID(v) if isinstance(v, str) else v for k, v in r.items()} for r in rows]
        imported = 0
        for i in range(0, len(parsed), CHUNK_SIZE):
            chunk = parsed[i : i + CHUNK_SIZE]
            stmt = pg_insert(assoc).values(chunk).on_conflict_do_nothing()
            result = await db.execute(stmt)
            imported += result.rowcount
        counts[name] = {"submitted": len(rows), "imported": imported}

    await db.commit()
    return {"counts": counts}
