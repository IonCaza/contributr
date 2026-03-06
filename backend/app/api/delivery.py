"""Delivery analytics API — work items, iterations, velocity, throughput, sync."""
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sse_starlette.sse import EventSourceResponse
import redis.asyncio as aioredis

from app.config import settings
from app.auth.dependencies import get_current_user
from app.db.base import get_db
from app.db.models.user import User
from app.db.models.work_item import WorkItem, WorkItemRelation
from app.db.models.iteration import Iteration
from app.db.models.delivery_sync_job import DeliverySyncJob
from app.db.models.sync_job import SyncStatus
from app.services.delivery_metrics import (
    get_delivery_stats,
    get_velocity,
    get_throughput_trend,
    get_iteration_detail,
)

router = APIRouter(prefix="/api/projects/{project_id}/delivery", tags=["delivery"])


# ── Stats ────────────────────────────────────────────────────────────

@router.get("/stats")
async def delivery_stats(
    project_id: uuid.UUID,
    team_id: uuid.UUID | None = None,
    contributor_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return await get_delivery_stats(
        db, project_id, team_id=team_id, contributor_id=contributor_id
    )


# ── Work Items ───────────────────────────────────────────────────────

@router.get("/work-items")
async def list_work_items(
    project_id: uuid.UUID,
    work_item_type: str | None = None,
    state: str | None = None,
    assignee_id: uuid.UUID | None = None,
    iteration_id: uuid.UUID | None = None,
    parent_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    q = (
        select(WorkItem)
        .where(WorkItem.project_id == project_id)
        .order_by(WorkItem.updated_at.desc())
    )
    if work_item_type:
        q = q.where(WorkItem.work_item_type == work_item_type)
    if state:
        q = q.where(WorkItem.state == state)
    if assignee_id:
        q = q.where(WorkItem.assigned_to_id == assignee_id)
    if iteration_id:
        q = q.where(WorkItem.iteration_id == iteration_id)
    if parent_id:
        child_ids = select(WorkItemRelation.target_work_item_id).where(
            WorkItemRelation.source_work_item_id == parent_id,
            WorkItemRelation.relation_type == "child",
        )
        q = q.where(WorkItem.id.in_(child_ids))

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    rows = (await db.execute(q.offset((page - 1) * page_size).limit(page_size))).scalars().all()

    items = []
    for wi in rows:
        children_count_q = select(func.count()).where(
            WorkItemRelation.source_work_item_id == wi.id,
            WorkItemRelation.relation_type == "child",
        )
        children_count = (await db.execute(children_count_q)).scalar() or 0

        parent_q = select(WorkItemRelation.source_work_item_id).where(
            WorkItemRelation.target_work_item_id == wi.id,
            WorkItemRelation.relation_type == "child",
        ).limit(1)
        parent_row = (await db.execute(parent_q)).scalar_one_or_none()

        items.append({
            "id": str(wi.id),
            "platform_work_item_id": wi.platform_work_item_id,
            "work_item_type": wi.work_item_type.value if hasattr(wi.work_item_type, "value") else wi.work_item_type,
            "title": wi.title,
            "state": wi.state,
            "assigned_to": {
                "id": str(wi.assigned_to_id),
                "name": None,
            } if wi.assigned_to_id else None,
            "iteration_id": str(wi.iteration_id) if wi.iteration_id else None,
            "story_points": wi.story_points,
            "priority": wi.priority,
            "tags": wi.tags or [],
            "created_at": wi.created_at.isoformat() if wi.created_at else "",
            "resolved_at": wi.resolved_at.isoformat() if wi.resolved_at else None,
            "closed_at": wi.closed_at.isoformat() if wi.closed_at else None,
            "platform_url": wi.platform_url,
            "children_count": children_count,
            "parent_id": str(parent_row) if parent_row else None,
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/work-items/{work_item_id}")
async def get_work_item(
    project_id: uuid.UUID,
    work_item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(WorkItem).where(
            WorkItem.id == work_item_id, WorkItem.project_id == project_id,
        )
    )
    wi = result.scalar_one_or_none()
    if not wi:
        raise HTTPException(404, "Work item not found")

    children_q = (
        select(WorkItem)
        .join(WorkItemRelation, WorkItemRelation.target_work_item_id == WorkItem.id)
        .where(
            WorkItemRelation.source_work_item_id == wi.id,
            WorkItemRelation.relation_type == "child",
        )
    )
    children = (await db.execute(children_q)).scalars().all()

    parent_q = (
        select(WorkItem)
        .join(WorkItemRelation, WorkItemRelation.source_work_item_id == WorkItem.id)
        .where(
            WorkItemRelation.target_work_item_id == wi.id,
            WorkItemRelation.relation_type == "child",
        )
    )
    parent = (await db.execute(parent_q)).scalar_one_or_none()

    return {
        "id": str(wi.id),
        "platform_work_item_id": wi.platform_work_item_id,
        "work_item_type": wi.work_item_type.value if hasattr(wi.work_item_type, "value") else wi.work_item_type,
        "title": wi.title,
        "state": wi.state,
        "assigned_to_id": str(wi.assigned_to_id) if wi.assigned_to_id else None,
        "created_by_id": str(wi.created_by_id) if wi.created_by_id else None,
        "area_path": wi.area_path,
        "iteration_id": str(wi.iteration_id) if wi.iteration_id else None,
        "story_points": wi.story_points,
        "priority": wi.priority,
        "tags": wi.tags or [],
        "state_changed_at": wi.state_changed_at.isoformat() if wi.state_changed_at else None,
        "activated_at": wi.activated_at.isoformat() if wi.activated_at else None,
        "resolved_at": wi.resolved_at.isoformat() if wi.resolved_at else None,
        "closed_at": wi.closed_at.isoformat() if wi.closed_at else None,
        "created_at": wi.created_at.isoformat() if wi.created_at else "",
        "updated_at": wi.updated_at.isoformat() if wi.updated_at else "",
        "platform_url": wi.platform_url,
        "parent": {
            "id": str(parent.id),
            "title": parent.title,
            "work_item_type": parent.work_item_type.value if hasattr(parent.work_item_type, "value") else parent.work_item_type,
        } if parent else None,
        "children": [
            {
                "id": str(c.id),
                "title": c.title,
                "work_item_type": c.work_item_type.value if hasattr(c.work_item_type, "value") else c.work_item_type,
                "state": c.state,
                "story_points": c.story_points,
            }
            for c in children
        ],
    }


# ── Iterations ───────────────────────────────────────────────────────

@router.get("/iterations")
async def list_iterations(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Iteration)
        .where(Iteration.project_id == project_id)
        .order_by(Iteration.start_date.desc().nullslast())
    )
    iters = result.scalars().all()
    out = []
    for it in iters:
        stats = await get_iteration_detail(db, it.id)
        out.append({
            "id": str(it.id),
            "name": it.name,
            "path": it.path,
            "start_date": it.start_date.isoformat() if it.start_date else None,
            "end_date": it.end_date.isoformat() if it.end_date else None,
            "stats": stats,
        })
    return out


@router.get("/iterations/{iteration_id}")
async def get_iteration(
    project_id: uuid.UUID,
    iteration_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Iteration).where(
            Iteration.id == iteration_id, Iteration.project_id == project_id,
        )
    )
    it = result.scalar_one_or_none()
    if not it:
        raise HTTPException(404, "Iteration not found")
    stats = await get_iteration_detail(db, it.id)
    return {
        "id": str(it.id),
        "name": it.name,
        "path": it.path,
        "start_date": it.start_date.isoformat() if it.start_date else None,
        "end_date": it.end_date.isoformat() if it.end_date else None,
        "stats": stats,
    }


# ── Velocity & Trends ───────────────────────────────────────────────

@router.get("/velocity")
async def velocity(
    project_id: uuid.UUID,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return await get_velocity(db, project_id, limit=limit)


@router.get("/trends")
async def trends(
    project_id: uuid.UUID,
    days: int = Query(90, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return await get_throughput_trend(db, project_id, days=days)


# ── Sync ─────────────────────────────────────────────────────────────

@router.get("/sync-jobs")
async def list_delivery_sync_jobs(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(DeliverySyncJob)
        .where(DeliverySyncJob.project_id == project_id)
        .order_by(DeliverySyncJob.created_at.desc())
        .limit(20)
    )
    jobs = result.scalars().all()
    return [
        {
            "id": str(j.id),
            "status": j.status.value if hasattr(j.status, "value") else j.status,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "finished_at": j.finished_at.isoformat() if j.finished_at else None,
            "error_message": j.error_message,
            "created_at": j.created_at.isoformat(),
        }
        for j in jobs
    ]


@router.post("/sync")
async def trigger_delivery_sync(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    running = await db.execute(
        select(DeliverySyncJob).where(
            DeliverySyncJob.project_id == project_id,
            DeliverySyncJob.status.in_([SyncStatus.QUEUED, SyncStatus.RUNNING]),
        )
    )
    if running.scalars().first():
        raise HTTPException(status_code=409, detail="Delivery sync already in progress")

    job = DeliverySyncJob(project_id=project_id, status=SyncStatus.QUEUED)
    db.add(job)
    await db.flush()

    from app.workers.tasks import sync_delivery
    task = sync_delivery.delay(str(project_id), str(job.id))
    job.celery_task_id = task.id
    await db.commit()

    return {"task_id": task.id, "job_id": str(job.id), "status": "queued"}


@router.get("/sync/logs")
async def stream_delivery_sync_logs(
    request: Request,
    project_id: uuid.UUID,
    token: str | None = Query(default=None),
):
    """Stream delivery sync logs in real-time via Server-Sent Events."""
    from app.auth.security import decode_token as decode_jwt
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token required")
    payload = decode_jwt(token)
    if payload is None or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    list_key = f"sync:logs:delivery-{project_id}"
    channel_key = f"sync:logs:live:delivery-{project_id}"

    async def event_generator():
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        try:
            existing = await r.lrange(list_key, 0, -1)
            for entry in existing:
                data = json.loads(entry)
                if data.get("phase") == "__done__":
                    yield {"event": "done", "data": entry}
                    return
                yield {"event": "log", "data": entry}

            pubsub = r.pubsub()
            await pubsub.subscribe(channel_key)
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if msg is None:
                        continue
                    data = json.loads(msg["data"])
                    if data.get("phase") == "__done__":
                        yield {"event": "done", "data": msg["data"]}
                        break
                    yield {"event": "log", "data": msg["data"]}
            finally:
                await pubsub.unsubscribe(channel_key)
                await pubsub.aclose()
        finally:
            await r.aclose()

    return EventSourceResponse(event_generator())
