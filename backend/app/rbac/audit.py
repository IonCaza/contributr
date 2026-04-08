"""Fire-and-forget audit logging for access-control decisions."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def log_access(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    action: str,
    outcome: str = "allowed",
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """Write an access audit record.  Best-effort — exceptions are swallowed."""
    try:
        from app.db.models.access_audit_log import AccessAuditLog
        entry = AccessAuditLog(
            user_id=user_id,
            action=action,
            outcome=outcome,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail,
            ip_address=ip_address,
        )
        db.add(entry)
        await db.flush()
    except Exception:
        logger.debug("Failed to write access audit log", exc_info=True)
