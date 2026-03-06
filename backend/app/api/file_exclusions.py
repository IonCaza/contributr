import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.db.models import User, FileExclusionPattern
from app.db.models.file_exclusion import DEFAULT_PATTERNS
from app.auth.dependencies import get_current_user

router = APIRouter(tags=["file-exclusions"])


class PatternCreate(BaseModel):
    pattern: str
    description: str | None = None
    enabled: bool = True


class PatternUpdate(BaseModel):
    enabled: bool | None = None
    description: str | None = None


@router.get("/file-exclusions")
async def list_patterns(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(FileExclusionPattern).order_by(FileExclusionPattern.pattern)
    )
    rows = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "pattern": r.pattern,
            "description": r.description,
            "enabled": r.enabled,
            "is_default": r.is_default,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.post("/file-exclusions", status_code=status.HTTP_201_CREATED)
async def create_pattern(
    body: PatternCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    existing = await db.execute(
        select(FileExclusionPattern).where(FileExclusionPattern.pattern == body.pattern)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Pattern already exists")

    p = FileExclusionPattern(
        pattern=body.pattern,
        description=body.description,
        enabled=body.enabled,
        is_default=False,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return {
        "id": str(p.id),
        "pattern": p.pattern,
        "description": p.description,
        "enabled": p.enabled,
        "is_default": p.is_default,
    }


@router.put("/file-exclusions/{pattern_id}")
async def update_pattern(
    pattern_id: uuid.UUID,
    body: PatternUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(FileExclusionPattern).where(FileExclusionPattern.id == pattern_id)
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Pattern not found")
    if body.enabled is not None:
        p.enabled = body.enabled
    if body.description is not None:
        p.description = body.description
    await db.commit()
    return {
        "id": str(p.id),
        "pattern": p.pattern,
        "description": p.description,
        "enabled": p.enabled,
        "is_default": p.is_default,
    }


@router.delete("/file-exclusions/{pattern_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pattern(
    pattern_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(FileExclusionPattern).where(FileExclusionPattern.id == pattern_id)
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Pattern not found")
    await db.delete(p)
    await db.commit()


@router.post("/file-exclusions/load-defaults")
async def load_defaults(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    existing = await db.execute(select(FileExclusionPattern.pattern))
    existing_patterns = set(existing.scalars().all())
    added = 0
    for pattern, desc in DEFAULT_PATTERNS:
        if pattern not in existing_patterns:
            db.add(FileExclusionPattern(
                pattern=pattern,
                description=desc,
                enabled=True,
                is_default=True,
            ))
            added += 1
    await db.commit()
    return {"added": added}


@router.get("/file-exclusions/active-patterns")
async def get_active_patterns(
    db: AsyncSession = Depends(get_db),
):
    """Return just the enabled pattern strings — used internally by the sync pipeline."""
    result = await db.execute(
        select(FileExclusionPattern.pattern).where(FileExclusionPattern.enabled.is_(True))
    )
    return result.scalars().all()
