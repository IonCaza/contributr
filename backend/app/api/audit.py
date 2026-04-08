"""Admin API for viewing access audit logs."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.db.base import get_db
from app.db.models.access_audit_log import AccessAuditLog
from app.db.models.user import User

router = APIRouter(prefix="/api/audit/access", tags=["audit"])


class AuditLogEntry(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    action: str
    resource_type: str | None
    resource_id: str | None
    outcome: str
    detail: dict | None
    ip_address: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class PaginatedAuditLogs(BaseModel):
    items: list[AuditLogEntry]
    total: int
    page: int
    page_size: int


@router.get("", response_model=PaginatedAuditLogs)
async def list_audit_logs(
    user_id: uuid.UUID | None = None,
    action: str | None = None,
    outcome: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    stmt = select(AccessAuditLog)
    if user_id:
        stmt = stmt.where(AccessAuditLog.user_id == user_id)
    if action:
        stmt = stmt.where(AccessAuditLog.action == action)
    if outcome:
        stmt = stmt.where(AccessAuditLog.outcome == outcome)
    stmt = stmt.order_by(AccessAuditLog.created_at.desc())

    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = (await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return PaginatedAuditLogs(items=items, total=total or 0, page=page, page_size=page_size)
