import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.db.models import User, Project
from app.db.models.project_schedule import ProjectSchedule, ScheduleInterval
from app.auth.dependencies import get_current_user

router = APIRouter(
    prefix="/api/projects/{project_id}/schedules",
    tags=["project-schedules"],
)

_VALID_INTERVALS = {e.value for e in ScheduleInterval}
_INTERVAL_FIELDS = {
    "repo_sync_interval", "delivery_sync_interval", "security_scan_interval",
    "dependency_scan_interval", "insights_interval",
}


class ProjectScheduleOut(BaseModel):
    repo_sync_interval: str
    repo_sync_last_run_at: datetime | None = None
    delivery_sync_interval: str
    delivery_sync_last_run_at: datetime | None = None
    security_scan_interval: str
    security_scan_last_run_at: datetime | None = None
    dependency_scan_interval: str
    dependency_scan_last_run_at: datetime | None = None
    insights_interval: str
    insights_last_run_at: datetime | None = None
    model_config = {"from_attributes": True}


class ProjectScheduleUpdate(BaseModel):
    repo_sync_interval: str | None = None
    delivery_sync_interval: str | None = None
    security_scan_interval: str | None = None
    dependency_scan_interval: str | None = None
    insights_interval: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def validate_interval(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_INTERVALS:
            raise ValueError(f"Invalid interval: {v}. Must be one of: {', '.join(sorted(_VALID_INTERVALS))}")
        return v


async def _get_project(db: AsyncSession, project_id: uuid.UUID) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


async def _get_or_create_schedule(db: AsyncSession, project_id: uuid.UUID) -> ProjectSchedule:
    result = await db.execute(
        select(ProjectSchedule).where(ProjectSchedule.project_id == project_id)
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        schedule = ProjectSchedule(project_id=project_id)
        db.add(schedule)
        await db.flush()
    return schedule


@router.get("", response_model=ProjectScheduleOut)
async def get_schedule(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_project(db, project_id)
    schedule = await _get_or_create_schedule(db, project_id)
    await db.commit()
    return schedule


@router.put("", response_model=ProjectScheduleOut)
async def update_schedule(
    project_id: uuid.UUID,
    body: ProjectScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_project(db, project_id)
    schedule = await _get_or_create_schedule(db, project_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        if field in _INTERVAL_FIELDS and value is not None:
            setattr(schedule, field, str(value))
    await db.commit()
    await db.refresh(schedule)
    return schedule
