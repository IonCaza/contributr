"""Teams CRUD + member management API."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user, get_accessible_project_ids
from app.db.base import get_db
from app.db.models.user import User
from app.db.models.team import Team, TeamMember
from app.db.models.contributor import Contributor

router = APIRouter(prefix="/api/teams", tags=["teams"])


# ── Schemas ──────────────────────────────────────────────────────────

class TeamCreate(BaseModel):
    project_id: uuid.UUID
    name: str
    description: str | None = None

class TeamUpdate(BaseModel):
    name: str | None = None
    description: str | None = None

class MemberAdd(BaseModel):
    contributor_id: uuid.UUID
    role: str = "member"

class TeamOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str | None
    platform: str | None
    member_count: int
    created_at: str
    updated_at: str

class MemberOut(BaseModel):
    contributor_id: uuid.UUID
    contributor_name: str
    contributor_email: str
    role: str
    joined_at: str


# ── Helpers ──────────────────────────────────────────────────────────

def _team_out(team: Team, member_count: int) -> dict:
    return {
        "id": team.id,
        "project_id": team.project_id,
        "name": team.name,
        "description": team.description,
        "platform": team.platform,
        "member_count": member_count,
        "created_at": team.created_at.isoformat() if team.created_at else "",
        "updated_at": team.updated_at.isoformat() if team.updated_at else "",
    }


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("")
async def list_teams(
    project_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
    accessible: set[uuid.UUID] | None = Depends(get_accessible_project_ids),
):
    q = select(Team).options(selectinload(Team.members))
    if project_id:
        if accessible is not None and project_id not in accessible:
            raise HTTPException(403, "No access to this project")
        q = q.where(Team.project_id == project_id)
    elif accessible is not None:
        q = q.where(Team.project_id.in_(accessible))
    q = q.order_by(Team.name)
    result = await db.execute(q)
    teams = result.scalars().all()
    return [_team_out(t, len(t.members)) for t in teams]


def _check_team_access(team: Team, accessible: set[uuid.UUID] | None) -> None:
    if accessible is not None and team.project_id not in accessible:
        raise HTTPException(403, "No access to this project")


@router.get("/{team_id}")
async def get_team(
    team_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
    accessible: set[uuid.UUID] | None = Depends(get_accessible_project_ids),
):
    result = await db.execute(
        select(Team).options(selectinload(Team.members)).where(Team.id == team_id)
    )
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(404, "Team not found")
    _check_team_access(team, accessible)
    return _team_out(team, len(team.members))


@router.post("/", status_code=201)
async def create_team(
    body: TeamCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
    accessible: set[uuid.UUID] | None = Depends(get_accessible_project_ids),
):
    if accessible is not None and body.project_id not in accessible:
        raise HTTPException(403, "No access to this project")
    team = Team(
        project_id=body.project_id,
        name=body.name,
        description=body.description,
    )
    db.add(team)
    await db.commit()
    await db.refresh(team)
    return _team_out(team, 0)


@router.put("/{team_id}")
async def update_team(
    team_id: uuid.UUID,
    body: TeamUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(404, "Team not found")
    if body.name is not None:
        team.name = body.name
    if body.description is not None:
        team.description = body.description
    team.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(team)
    count_q = select(func.count()).select_from(TeamMember).where(TeamMember.team_id == team.id)
    mc = (await db.execute(count_q)).scalar() or 0
    return _team_out(team, mc)


@router.delete("/{team_id}", status_code=204)
async def delete_team(
    team_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(404, "Team not found")
    await db.delete(team)
    await db.commit()


@router.get("/{team_id}/members")
async def list_members(
    team_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(TeamMember, Contributor)
        .join(Contributor, TeamMember.contributor_id == Contributor.id)
        .where(TeamMember.team_id == team_id)
        .order_by(Contributor.canonical_name)
    )
    return [
        {
            "contributor_id": tm.contributor_id,
            "contributor_name": c.canonical_name,
            "contributor_email": c.canonical_email,
            "role": tm.role,
            "joined_at": tm.joined_at.isoformat() if tm.joined_at else "",
        }
        for tm, c in result.all()
    ]


@router.post("/{team_id}/members", status_code=201)
async def add_member(
    team_id: uuid.UUID,
    body: MemberAdd,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    existing = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.contributor_id == body.contributor_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Contributor is already a member of this team")
    tm = TeamMember(
        team_id=team_id,
        contributor_id=body.contributor_id,
        role=body.role,
    )
    db.add(tm)
    await db.commit()
    return {"status": "added"}


@router.delete("/{team_id}/members/{contributor_id}", status_code=204)
async def remove_member(
    team_id: uuid.UUID,
    contributor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.contributor_id == contributor_id,
        )
    )
    tm = result.scalar_one_or_none()
    if not tm:
        raise HTTPException(404, "Member not found")
    await db.delete(tm)
    await db.commit()
