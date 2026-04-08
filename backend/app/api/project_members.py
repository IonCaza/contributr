"""Project membership management: add/remove/change role for users within a project."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user
from app.db.base import get_db
from app.db.models.project import Project
from app.db.models.project_membership import ProjectMembership
from app.db.models.user import User

router = APIRouter(prefix="/projects/{project_id}/members", tags=["project-members"])

PROJECT_ROLES = ("owner", "admin", "member", "viewer")


def _role_rank(role: str) -> int:
    try:
        return PROJECT_ROLES.index(role)
    except ValueError:
        return len(PROJECT_ROLES)


class MemberResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: str | None
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AddMemberRequest(BaseModel):
    email: EmailStr | None = None
    user_id: uuid.UUID | None = None
    role: str = "member"


class UpdateRoleRequest(BaseModel):
    role: str


async def _get_caller_membership(
    db: AsyncSession, project_id: uuid.UUID, user: User,
) -> ProjectMembership | None:
    if user.is_admin:
        return ProjectMembership(
            user_id=user.id, project_id=project_id, role="owner",
        )
    result = await db.execute(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == user.id,
        )
    )
    return result.scalar_one_or_none()


async def _require_project_admin(
    db: AsyncSession, project_id: uuid.UUID, user: User,
) -> ProjectMembership:
    mem = await _get_caller_membership(db, project_id, user)
    if not mem or _role_rank(mem.role) > _role_rank("admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project admin access required")
    return mem


@router.get("", response_model=list[MemberResponse])
async def list_members(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ProjectMembership, User)
        .join(User, User.id == ProjectMembership.user_id)
        .where(ProjectMembership.project_id == project_id)
        .order_by(ProjectMembership.created_at)
    )
    return [
        MemberResponse(
            user_id=u.id,
            email=u.email,
            full_name=u.full_name,
            role=pm.role,
            created_at=pm.created_at,
        )
        for pm, u in result.all()
    ]


@router.post("", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def add_member(
    project_id: uuid.UUID,
    body: AddMemberRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    caller_mem = await _require_project_admin(db, project_id, user)

    if _role_rank(body.role) < _role_rank(caller_mem.role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot assign a higher role than your own")

    if body.user_id:
        target = await db.get(User, body.user_id)
    elif body.email:
        result = await db.execute(select(User).where(User.email == body.email))
        target = result.scalar_one_or_none()
    else:
        raise HTTPException(status_code=400, detail="Provide email or user_id")

    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    existing = await db.execute(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == target.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a project member")

    pm = ProjectMembership(
        user_id=target.id,
        project_id=project_id,
        role=body.role,
        invited_by_id=user.id,
    )
    db.add(pm)
    await db.commit()

    return MemberResponse(
        user_id=target.id,
        email=target.email,
        full_name=target.full_name,
        role=pm.role,
        created_at=pm.created_at,
    )


@router.patch("/{member_user_id}", response_model=MemberResponse)
async def update_member_role(
    project_id: uuid.UUID,
    member_user_id: uuid.UUID,
    body: UpdateRoleRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    caller_mem = await _require_project_admin(db, project_id, user)

    result = await db.execute(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == member_user_id,
        )
    )
    pm = result.scalar_one_or_none()
    if not pm:
        raise HTTPException(status_code=404, detail="Member not found")

    if pm.role == "owner" and body.role != "owner":
        raise HTTPException(status_code=400, detail="Cannot demote the project owner. Transfer ownership first.")

    if _role_rank(body.role) < _role_rank(caller_mem.role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot assign a higher role than your own")

    pm.role = body.role
    await db.commit()

    target = await db.get(User, member_user_id)
    return MemberResponse(
        user_id=pm.user_id,
        email=target.email if target else "",
        full_name=target.full_name if target else None,
        role=pm.role,
        created_at=pm.created_at,
    )


@router.delete("/{member_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    project_id: uuid.UUID,
    member_user_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_project_admin(db, project_id, user)

    if member_user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")

    result = await db.execute(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == member_user_id,
        )
    )
    pm = result.scalar_one_or_none()
    if not pm:
        raise HTTPException(status_code=404, detail="Member not found")

    if pm.role == "owner":
        raise HTTPException(status_code=400, detail="Cannot remove the project owner")

    await db.delete(pm)
    await db.commit()
