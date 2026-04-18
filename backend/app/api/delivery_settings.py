"""CRUD API for per-project delivery analytics settings."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.base import get_db
from app.db.models import Project, User
from app.db.models.project_delivery_settings import (
    DEFAULT_CYCLE_END_STATES,
    DEFAULT_CYCLE_START_STATES,
    DEFAULT_HEALTH_THRESHOLDS,
    DEFAULT_READY_STATES,
    DEFAULT_REVIEW_STATES,
    DEFAULT_TESTING_STATES,
    ProjectDeliverySettings,
)
from app.db.models.work_item import WorkItem

router = APIRouter(
    prefix="/api/projects/{project_id}/delivery-settings",
    tags=["delivery-settings"],
)


class DeliverySettingsOut(BaseModel):
    cycle_time_start_states: list[str]
    cycle_time_end_states: list[str]
    review_states: list[str]
    testing_states: list[str]
    ready_states: list[str]
    tshirt_custom_field: str | None = None
    backlog_health_thresholds: dict
    long_running_threshold_days: int
    rolling_capacity_sprints: int
    updated_at: datetime | None = None
    model_config = {"from_attributes": True}


class DeliverySettingsUpdate(BaseModel):
    cycle_time_start_states: list[str] | None = None
    cycle_time_end_states: list[str] | None = None
    review_states: list[str] | None = None
    testing_states: list[str] | None = None
    ready_states: list[str] | None = None
    tshirt_custom_field: str | None = None
    backlog_health_thresholds: dict | None = None
    long_running_threshold_days: int | None = Field(default=None, ge=1, le=365)
    rolling_capacity_sprints: int | None = Field(default=None, ge=1, le=20)


async def _get_project(db: AsyncSession, project_id: uuid.UUID) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project


async def get_or_create_delivery_settings(
    db: AsyncSession, project_id: uuid.UUID,
) -> ProjectDeliverySettings:
    """Fetch the settings row for a project, creating defaults if none exists."""
    result = await db.execute(
        select(ProjectDeliverySettings).where(
            ProjectDeliverySettings.project_id == project_id
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = ProjectDeliverySettings(
            project_id=project_id,
            cycle_time_start_states=list(DEFAULT_CYCLE_START_STATES),
            cycle_time_end_states=list(DEFAULT_CYCLE_END_STATES),
            review_states=list(DEFAULT_REVIEW_STATES),
            testing_states=list(DEFAULT_TESTING_STATES),
            ready_states=list(DEFAULT_READY_STATES),
            backlog_health_thresholds=dict(DEFAULT_HEALTH_THRESHOLDS),
        )
        db.add(row)
        await db.flush()
    return row


@router.get("", response_model=DeliverySettingsOut)
async def read_settings(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_project(db, project_id)
    row = await get_or_create_delivery_settings(db, project_id)
    await db.commit()
    return row


@router.put("", response_model=DeliverySettingsOut)
async def update_settings(
    project_id: uuid.UUID,
    body: DeliverySettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_project(db, project_id)
    row = await get_or_create_delivery_settings(db, project_id)

    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(row, key, value)

    await db.commit()
    await db.refresh(row)
    return row


@router.get("/available-states")
async def list_available_states(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Distinct state values observed across this project's work items.

    Used to populate the multi-select in the settings UI so operators can
    pick state names that actually exist in their data.
    """
    await _get_project(db, project_id)
    result = await db.execute(
        select(distinct(WorkItem.state))
        .where(WorkItem.project_id == project_id, WorkItem.state.isnot(None))
        .order_by(WorkItem.state)
    )
    states = [r[0] for r in result.all() if r[0]]
    return {"states": states}


@router.get("/available-custom-fields")
async def list_available_custom_fields(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Distinct keys found in any work item's ``custom_fields`` JSONB for this project.

    Lets the UI suggest candidates for the t-shirt field mapping.
    """
    from sqlalchemy import text

    await _get_project(db, project_id)
    result = await db.execute(
        text(
            """
            SELECT DISTINCT jsonb_object_keys(custom_fields) AS key
            FROM work_items
            WHERE project_id = :project_id AND custom_fields IS NOT NULL
            ORDER BY key
            """
        ),
        {"project_id": str(project_id)},
    )
    keys = [r[0] for r in result.all()]
    return {"keys": keys}
