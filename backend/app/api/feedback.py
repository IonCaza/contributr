"""Feedback API — create, list, update, delete feedback items."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.base import get_db
from app.db.models.user import User
from app.db.models.feedback import Feedback

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


# ── Schemas ───────────────────────────────────────────────────────────

class FeedbackCreate(BaseModel):
    source: str = "human"
    category: str | None = None
    content: str
    user_query: str | None = None
    agent_slug: str | None = None
    session_id: str | None = None
    message_id: str | None = None


class FeedbackUpdate(BaseModel):
    status: str | None = None
    admin_notes: str | None = None


class FeedbackOut(BaseModel):
    id: str
    source: str
    category: str | None
    content: str
    user_query: str | None
    agent_slug: str | None
    session_id: str | None
    user_id: str | None
    message_id: str | None
    status: str
    admin_notes: str | None
    created_at: str
    updated_at: str


class PaginatedFeedback(BaseModel):
    items: list[FeedbackOut]
    total: int


def _row_to_out(row: Feedback) -> FeedbackOut:
    return FeedbackOut(
        id=str(row.id),
        source=str(row.source),
        category=row.category,
        content=row.content,
        user_query=row.user_query,
        agent_slug=row.agent_slug,
        session_id=str(row.session_id) if row.session_id else None,
        user_id=str(row.user_id) if row.user_id else None,
        message_id=str(row.message_id) if row.message_id else None,
        status=str(row.status),
        admin_notes=row.admin_notes,
        created_at=row.created_at.isoformat() if isinstance(row.created_at, datetime) else str(row.created_at),
        updated_at=row.updated_at.isoformat() if isinstance(row.updated_at, datetime) else str(row.updated_at),
    )


# ── Create ────────────────────────────────────────────────────────────

@router.post("", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
async def create_feedback(
    body: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = Feedback(
        source=body.source,
        category=body.category,
        content=body.content,
        user_query=body.user_query,
        agent_slug=body.agent_slug,
        session_id=uuid.UUID(body.session_id) if body.session_id else None,
        message_id=uuid.UUID(body.message_id) if body.message_id else None,
        user_id=user.id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _row_to_out(row)


# ── List (paginated + filtered) ──────────────────────────────────────

@router.get("", response_model=PaginatedFeedback)
async def list_feedback(
    source: str | None = Query(None),
    feedback_status: str | None = Query(None, alias="status"),
    agent_slug: str | None = Query(None),
    category: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    q = select(Feedback)
    count_q = select(func.count(Feedback.id))

    if source:
        q = q.where(Feedback.source == source)
        count_q = count_q.where(Feedback.source == source)
    if feedback_status:
        q = q.where(Feedback.status == feedback_status)
        count_q = count_q.where(Feedback.status == feedback_status)
    if agent_slug:
        q = q.where(Feedback.agent_slug == agent_slug)
        count_q = count_q.where(Feedback.agent_slug == agent_slug)
    if category:
        q = q.where(Feedback.category == category)
        count_q = count_q.where(Feedback.category == category)

    total = (await db.execute(count_q)).scalar_one()
    result = await db.execute(
        q.order_by(Feedback.created_at.desc()).offset(skip).limit(limit)
    )
    rows = result.scalars().all()

    return PaginatedFeedback(
        items=[_row_to_out(r) for r in rows],
        total=total,
    )


# ── Get single ────────────────────────────────────────────────────────

@router.get("/{feedback_id}", response_model=FeedbackOut)
async def get_feedback(
    feedback_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    row = await db.get(Feedback, feedback_id)
    if not row:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return _row_to_out(row)


# ── Update ────────────────────────────────────────────────────────────

@router.patch("/{feedback_id}", response_model=FeedbackOut)
async def update_feedback(
    feedback_id: uuid.UUID,
    body: FeedbackUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    row = await db.get(Feedback, feedback_id)
    if not row:
        raise HTTPException(status_code=404, detail="Feedback not found")

    if body.status is not None:
        row.status = body.status
    if body.admin_notes is not None:
        row.admin_notes = body.admin_notes

    await db.commit()
    await db.refresh(row)
    return _row_to_out(row)


# ── Delete ────────────────────────────────────────────────────────────

@router.delete("/{feedback_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feedback(
    feedback_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    row = await db.get(Feedback, feedback_id)
    if not row:
        raise HTTPException(status_code=404, detail="Feedback not found")
    await db.delete(row)
    await db.commit()
