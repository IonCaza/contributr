"""CRUD API for access-policy management (platform + project admin)."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_admin
from app.db.base import get_db
from app.db.models.access_policy import AccessPolicy
from app.db.models.user import User

router = APIRouter(prefix="/api/access-policies", tags=["access-policies"])


class PolicyResponse(BaseModel):
    id: uuid.UUID
    scope_type: str
    scope_id: uuid.UUID | None
    data_scope: str | None
    agent_tool_rules: dict | None
    sql_allowed_tables: list[str] | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class PolicyCreate(BaseModel):
    scope_type: str
    scope_id: uuid.UUID | None = None
    data_scope: str | None = "all"
    agent_tool_rules: dict | None = None
    sql_allowed_tables: list[str] | None = None


class PolicyUpdate(BaseModel):
    data_scope: str | None = None
    agent_tool_rules: dict | None = None
    sql_allowed_tables: list[str] | None = None


VALID_SCOPES = {"platform", "organization", "team", "project", "user"}
VALID_DATA_SCOPES = {"own", "team", "org", "all"}


@router.get("", response_model=list[PolicyResponse])
async def list_policies(
    scope_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    stmt = select(AccessPolicy).order_by(AccessPolicy.scope_type, AccessPolicy.created_at)
    if scope_type:
        stmt = stmt.where(AccessPolicy.scope_type == scope_type)
    return (await db.execute(stmt)).scalars().all()


@router.get("/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    policy = await db.get(AccessPolicy, policy_id)
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
    return policy


@router.post("", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(
    body: PolicyCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if body.scope_type not in VALID_SCOPES:
        raise HTTPException(status_code=422, detail=f"scope_type must be one of {VALID_SCOPES}")
    if body.data_scope and body.data_scope not in VALID_DATA_SCOPES:
        raise HTTPException(status_code=422, detail=f"data_scope must be one of {VALID_DATA_SCOPES}")

    existing = await db.execute(
        select(AccessPolicy).where(
            AccessPolicy.scope_type == body.scope_type,
            AccessPolicy.scope_id == body.scope_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Policy for this scope already exists")

    policy = AccessPolicy(
        scope_type=body.scope_type,
        scope_id=body.scope_id,
        data_scope=body.data_scope,
        agent_tool_rules=body.agent_tool_rules,
        sql_allowed_tables=body.sql_allowed_tables,
        created_by_id=admin.id,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return policy


@router.put("/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: uuid.UUID,
    body: PolicyUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    policy = await db.get(AccessPolicy, policy_id)
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")

    if body.data_scope is not None:
        if body.data_scope not in VALID_DATA_SCOPES:
            raise HTTPException(status_code=422, detail=f"data_scope must be one of {VALID_DATA_SCOPES}")
        policy.data_scope = body.data_scope
    if body.agent_tool_rules is not None:
        policy.agent_tool_rules = body.agent_tool_rules
    if body.sql_allowed_tables is not None:
        policy.sql_allowed_tables = body.sql_allowed_tables

    await db.commit()
    await db.refresh(policy)
    return policy


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(
    policy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    policy = await db.get(AccessPolicy, policy_id)
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
    await db.delete(policy)
    await db.commit()
