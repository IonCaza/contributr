"""Delivery analytics API — work items, iterations, velocity, throughput, sync."""
from __future__ import annotations

import json
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, func, case, String
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
from app.db.models.work_item_commit import WorkItemCommit
from app.db.models.commit import Commit
from app.db.models.contributor import Contributor
from app.db.models.team import Team, TeamMember
from app.services.delivery_metrics import (
    DeliveryFilters,
    get_delivery_stats,
    get_velocity,
    get_throughput_trend,
    get_iteration_detail,
    get_sprint_burndown,
    get_cycle_time_distribution,
    get_wip_by_state,
    get_cumulative_flow,
    get_stale_backlog,
    get_backlog_age_distribution,
    get_backlog_growth,
    get_bug_trend,
    get_bug_resolution_time,
    get_defect_density,
    get_intersection_metrics,
    get_work_item_details,
    get_contributor_delivery_summary,
)

router = APIRouter(prefix="/api/projects/{project_id}/delivery", tags=["delivery"])


# ── Stats ────────────────────────────────────────────────────────────

@router.get("/stats")
async def delivery_stats(
    project_id: uuid.UUID,
    team_id: uuid.UUID | None = None,
    contributor_id: uuid.UUID | None = None,
    iteration_ids: list[str] | None = Query(None),
    from_date: date | None = None,
    to_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    filters = DeliveryFilters(
        iteration_ids=[uuid.UUID(i) for i in iteration_ids] if iteration_ids else None,
        from_date=from_date,
        to_date=to_date,
        team_id=team_id,
        contributor_id=contributor_id,
    )
    return await get_delivery_stats(db, project_id, filters=filters)


# ── Work Items ───────────────────────────────────────────────────────

@router.get("/work-items")
async def list_work_items(
    project_id: uuid.UUID,
    work_item_type: str | None = None,
    state: str | None = None,
    assignee_id: uuid.UUID | None = None,
    iteration_ids: list[str] | None = Query(None),
    parent_id: uuid.UUID | None = None,
    search: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    q = (
        select(WorkItem)
        .options(selectinload(WorkItem.assigned_to), selectinload(WorkItem.iteration))
        .where(WorkItem.project_id == project_id)
        .order_by(WorkItem.updated_at.desc())
    )
    if search:
        term = f"%{search}%"
        q = q.where(
            WorkItem.title.ilike(term) | WorkItem.platform_work_item_id.cast(String).ilike(term)
        )
    if work_item_type:
        q = q.where(WorkItem.work_item_type == work_item_type)
    if state:
        q = q.where(WorkItem.state == state)
    if assignee_id:
        q = q.where(WorkItem.assigned_to_id == assignee_id)
    if iteration_ids:
        q = q.where(WorkItem.iteration_id.in_([uuid.UUID(i) for i in iteration_ids]))
    if from_date is not None:
        q = q.where(WorkItem.created_at >= from_date)
    if to_date is not None:
        q = q.where(WorkItem.created_at <= to_date)
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
                "name": wi.assigned_to.canonical_name if wi.assigned_to else None,
            } if wi.assigned_to_id else None,
            "iteration_id": str(wi.iteration_id) if wi.iteration_id else None,
            "iteration_name": wi.iteration.name if wi.iteration else None,
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
        select(WorkItem)
        .options(
            selectinload(WorkItem.assigned_to),
            selectinload(WorkItem.created_by),
            selectinload(WorkItem.iteration),
        )
        .where(WorkItem.id == work_item_id, WorkItem.project_id == project_id)
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

    commit_links_q = (
        select(WorkItemCommit, Commit, Contributor)
        .join(Commit, WorkItemCommit.commit_id == Commit.id)
        .outerjoin(Contributor, Commit.contributor_id == Contributor.id)
        .where(WorkItemCommit.work_item_id == wi.id)
        .order_by(Commit.authored_at.desc())
    )
    commit_link_rows = (await db.execute(commit_links_q)).all()
    linked_commits = [
        {
            "id": str(wic.id),
            "sha": c.sha,
            "message": c.message,
            "authored_at": c.authored_at.isoformat() if c.authored_at else None,
            "link_type": wic.link_type,
            "contributor": {"id": str(contrib.id), "name": contrib.canonical_name} if contrib else None,
        }
        for wic, c, contrib in commit_link_rows
    ]

    return {
        "id": str(wi.id),
        "platform_work_item_id": wi.platform_work_item_id,
        "work_item_type": wi.work_item_type.value if hasattr(wi.work_item_type, "value") else wi.work_item_type,
        "title": wi.title,
        "description": wi.description,
        "state": wi.state,
        "assigned_to": {
            "id": str(wi.assigned_to_id),
            "name": wi.assigned_to.canonical_name if wi.assigned_to else None,
        } if wi.assigned_to_id else None,
        "created_by": {
            "id": str(wi.created_by_id),
            "name": wi.created_by.canonical_name if wi.created_by else None,
        } if wi.created_by_id else None,
        "area_path": wi.area_path,
        "iteration": {
            "id": str(wi.iteration_id),
            "name": wi.iteration.name if wi.iteration else None,
        } if wi.iteration_id else None,
        "story_points": wi.story_points,
        "priority": wi.priority,
        "tags": wi.tags or [],
        "custom_fields": wi.custom_fields,
        "original_estimate": wi.original_estimate,
        "remaining_work": wi.remaining_work,
        "completed_work": wi.completed_work,
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
        "linked_commits": linked_commits,
    }


@router.get("/work-items/{work_item_id}/commits")
async def get_work_item_commits(
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
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Work item not found")

    q = (
        select(WorkItemCommit, Commit, Contributor)
        .join(Commit, WorkItemCommit.commit_id == Commit.id)
        .outerjoin(Contributor, Commit.contributor_id == Contributor.id)
        .where(WorkItemCommit.work_item_id == work_item_id)
        .order_by(Commit.authored_at.desc())
    )
    rows = (await db.execute(q)).all()
    return [
        {
            "id": str(wic.id),
            "sha": c.sha,
            "message": c.message,
            "authored_at": c.authored_at.isoformat() if c.authored_at else None,
            "link_type": wic.link_type,
            "contributor": {"id": str(contrib.id), "name": contrib.canonical_name} if contrib else None,
        }
        for wic, c, contrib in rows
    ]


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
    burndown = await get_sprint_burndown(db, iteration_id)

    wi_q = (
        select(WorkItem)
        .options(selectinload(WorkItem.assigned_to))
        .where(WorkItem.iteration_id == iteration_id)
        .order_by(WorkItem.updated_at.desc())
    )
    wi_rows = (await db.execute(wi_q)).scalars().all()
    work_items = [
        {
            "id": str(w.id),
            "platform_work_item_id": w.platform_work_item_id,
            "work_item_type": w.work_item_type.value if hasattr(w.work_item_type, "value") else w.work_item_type,
            "title": w.title,
            "state": w.state,
            "story_points": w.story_points,
            "assigned_to": {
                "id": str(w.assigned_to_id),
                "name": w.assigned_to.canonical_name if w.assigned_to else None,
            } if w.assigned_to_id else None,
        }
        for w in wi_rows
    ]

    contrib_q = (
        select(
            WorkItem.assigned_to_id,
            func.count().label("total"),
            func.sum(case((WorkItem.resolved_at.isnot(None), 1), else_=0)).label("completed"),
        )
        .where(WorkItem.iteration_id == iteration_id, WorkItem.assigned_to_id.isnot(None))
        .group_by(WorkItem.assigned_to_id)
    )
    contrib_rows = (await db.execute(contrib_q)).all()
    contrib_ids = [r[0] for r in contrib_rows]
    contrib_names: dict = {}
    if contrib_ids:
        name_rows = (await db.execute(
            select(Contributor.id, Contributor.canonical_name).where(Contributor.id.in_(contrib_ids))
        )).all()
        contrib_names = {r[0]: r[1] for r in name_rows}
    contributors = [
        {
            "id": str(r[0]),
            "name": contrib_names.get(r[0]),
            "total": r.total,
            "completed": r.completed,
        }
        for r in contrib_rows
    ]

    return {
        "id": str(it.id),
        "name": it.name,
        "path": it.path,
        "start_date": it.start_date.isoformat() if it.start_date else None,
        "end_date": it.end_date.isoformat() if it.end_date else None,
        "stats": stats,
        "burndown": burndown,
        "work_items": work_items,
        "contributors": contributors,
    }


# ── Velocity & Trends ───────────────────────────────────────────────

@router.get("/velocity")
async def velocity(
    project_id: uuid.UUID,
    limit: int = Query(10, ge=1, le=50),
    iteration_ids: list[str] | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    filters = DeliveryFilters(
        iteration_ids=[uuid.UUID(i) for i in iteration_ids] if iteration_ids else None,
    )
    return await get_velocity(db, project_id, filters=filters, limit=limit)


@router.get("/trends")
async def trends(
    project_id: uuid.UUID,
    days: int = Query(90, ge=7, le=365),
    from_date: date | None = None,
    to_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    filters = DeliveryFilters(from_date=from_date, to_date=to_date)
    return await get_throughput_trend(db, project_id, filters=filters, days=days)


# ── Teams ────────────────────────────────────────────────────────────

@router.get("/teams/{team_id}")
async def get_team(
    project_id: uuid.UUID,
    team_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Team).where(Team.id == team_id, Team.project_id == project_id)
    )
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(404, "Team not found")

    members_q = (
        select(TeamMember, Contributor)
        .join(Contributor, TeamMember.contributor_id == Contributor.id)
        .where(TeamMember.team_id == team_id)
    )
    member_rows = (await db.execute(members_q)).all()
    members = [
        {
            "id": str(contrib.id),
            "name": contrib.canonical_name,
            "email": contrib.canonical_email,
            "role": tm.role,
        }
        for tm, contrib in member_rows
    ]

    contributor_ids = [contrib.id for _, contrib in member_rows]
    work_item_summary: list[dict] = []
    if contributor_ids:
        summary_q = (
            select(WorkItem.state, func.count())
            .where(
                WorkItem.project_id == project_id,
                WorkItem.assigned_to_id.in_(contributor_ids),
            )
            .group_by(WorkItem.state)
        )
        summary_rows = (await db.execute(summary_q)).all()
        work_item_summary = [{"state": r[0], "count": r[1]} for r in summary_rows]

    return {
        "id": str(team.id),
        "name": team.name,
        "description": team.description,
        "platform": team.platform,
        "members": members,
        "work_item_summary": work_item_summary,
    }


# ── Metrics ──────────────────────────────────────────────────────────

def _build_delivery_filters(
    iteration_ids: list[str] | None,
    from_date: date | None,
    to_date: date | None,
    contributor_id: uuid.UUID | None = None,
) -> DeliveryFilters:
    return DeliveryFilters(
        iteration_ids=[uuid.UUID(i) for i in iteration_ids] if iteration_ids else None,
        from_date=from_date,
        to_date=to_date,
        contributor_id=contributor_id,
    )


@router.get("/metrics/flow")
async def flow_metrics(
    project_id: uuid.UUID,
    iteration_ids: list[str] | None = Query(None),
    from_date: date | None = None,
    to_date: date | None = None,
    contributor_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    filters = _build_delivery_filters(iteration_ids, from_date, to_date, contributor_id)
    return {
        "cycle_time_distribution": await get_cycle_time_distribution(db, project_id, filters=filters),
        "wip_by_state": await get_wip_by_state(db, project_id, filters=filters),
        "cumulative_flow": await get_cumulative_flow(db, project_id, filters=filters),
    }


@router.get("/metrics/backlog-health")
async def backlog_health_metrics(
    project_id: uuid.UUID,
    iteration_ids: list[str] | None = Query(None),
    from_date: date | None = None,
    to_date: date | None = None,
    contributor_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    filters = _build_delivery_filters(iteration_ids, from_date, to_date, contributor_id)
    return {
        "stale_items": await get_stale_backlog(db, project_id, filters=filters),
        "age_distribution": await get_backlog_age_distribution(db, project_id, filters=filters),
        "growth": await get_backlog_growth(db, project_id, filters=filters),
    }


@router.get("/metrics/quality")
async def quality_metrics(
    project_id: uuid.UUID,
    iteration_ids: list[str] | None = Query(None),
    from_date: date | None = None,
    to_date: date | None = None,
    contributor_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    filters = _build_delivery_filters(iteration_ids, from_date, to_date, contributor_id)
    dd = await get_defect_density(db, project_id, filters=filters)
    return {
        "bug_trend": await get_bug_trend(db, project_id, filters=filters),
        "resolution_time": await get_bug_resolution_time(db, project_id, filters=filters),
        "defect_density": {
            "bugs": dd["bug_count"],
            "total": dd["total_items"],
            "ratio": dd["defect_density_pct"] / 100 if dd["defect_density_pct"] else 0,
        },
    }


@router.get("/metrics/item-details")
async def item_details(
    project_id: uuid.UUID,
    iteration_ids: list[str] | None = Query(None),
    from_date: date | None = None,
    to_date: date | None = None,
    contributor_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    filters = _build_delivery_filters(iteration_ids, from_date, to_date, contributor_id)
    return await get_work_item_details(db, project_id, filters=filters)


@router.get("/metrics/contributor-summary")
async def contributor_summary(
    project_id: uuid.UUID,
    iteration_ids: list[str] | None = Query(None),
    from_date: date | None = None,
    to_date: date | None = None,
    contributor_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    filters = _build_delivery_filters(iteration_ids, from_date, to_date, contributor_id)
    return await get_contributor_delivery_summary(db, project_id, filters=filters)


@router.get("/intersection")
async def intersection_metrics(
    project_id: uuid.UUID,
    iteration_ids: list[str] | None = Query(None),
    from_date: date | None = None,
    to_date: date | None = None,
    contributor_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    filters = _build_delivery_filters(iteration_ids, from_date, to_date, contributor_id)
    return await get_intersection_metrics(db, project_id, filters=filters)


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
