"""Custom field configuration API — discover, list, bulk upsert, delete."""
from __future__ import annotations

import uuid
import logging
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.base import get_db
from app.db.models.user import User
from app.db.models.project import Project
from app.db.models.repository import Platform
from app.db.models.platform_credential import PlatformCredential
from app.db.models.custom_field_config import CustomFieldConfig
from app.api.platform_credentials import decrypt_token
from app.services.azure_workitems_client import (
    _get_connection, _parse_ado_project, KNOWN_FIELDS,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/projects/{project_id}/custom-fields",
    tags=["custom-fields"],
)

_executor = ThreadPoolExecutor(max_workers=2)


# ── Schemas ───────────────────────────────────────────────────────────

class DiscoveredField(BaseModel):
    reference_name: str
    name: str
    field_type: str
    is_configured: bool


class CustomFieldConfigOut(BaseModel):
    id: str
    project_id: str
    field_reference_name: str
    display_name: str
    field_type: str
    enabled: bool

    class Config:
        from_attributes = True


class CustomFieldConfigIn(BaseModel):
    field_reference_name: str
    display_name: str
    field_type: str = "string"
    enabled: bool = True


class BulkUpsertRequest(BaseModel):
    fields: list[CustomFieldConfigIn]


# ── Helpers ───────────────────────────────────────────────────────────

async def _resolve_ado_connection(
    db: AsyncSession, project: Project,
) -> tuple[str, str, str]:
    """Return (org_url, token, ado_project_name) or raise 400/404."""
    ado_project_name = _parse_ado_project(project)
    if not ado_project_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Azure DevOps repository found in project",
        )

    result = await db.execute(
        select(PlatformCredential)
        .where(PlatformCredential.platform == Platform.AZURE)
        .order_by(PlatformCredential.created_at.desc())
        .limit(1)
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Azure DevOps platform credential configured",
        )

    token = decrypt_token(cred.token_encrypted)

    azure_repo = next(
        (r for r in project.repositories if r.platform and r.platform.value == "azure"),
        None,
    )
    if azure_repo and azure_repo.platform_owner:
        org = azure_repo.platform_owner.split("/", 1)[0]
        org_url = cred.base_url or f"https://dev.azure.com/{org}"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot determine Azure DevOps organization URL",
        )

    return org_url, token, ado_project_name


def _fetch_fields_sync(org_url: str, token: str, ado_project_name: str):
    """Blocking call to ADO — run in a thread."""
    connection = _get_connection(org_url, token)
    wit_client = connection.clients.get_work_item_tracking_client()
    return wit_client.get_fields(ado_project_name)


# ── Discover ──────────────────────────────────────────────────────────

@router.get("/discover", response_model=list[DiscoveredField])
async def discover_fields(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Project).where(Project.id == project_id).options(
            selectinload(Project.repositories)
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    org_url, token, ado_project_name = await _resolve_ado_connection(db, project)

    import asyncio
    loop = asyncio.get_event_loop()
    ado_fields = await loop.run_in_executor(
        _executor, _fetch_fields_sync, org_url, token, ado_project_name
    )

    existing = await db.execute(
        select(CustomFieldConfig.field_reference_name)
        .where(CustomFieldConfig.project_id == project_id)
    )
    configured_refs = set(existing.scalars().all())

    discovered: list[DiscoveredField] = []
    for f in ado_fields:
        ref = getattr(f, "reference_name", None) or ""
        if ref in KNOWN_FIELDS:
            continue
        name = getattr(f, "name", ref)
        ftype = str(getattr(f, "type", "string") or "string").lower()
        discovered.append(DiscoveredField(
            reference_name=ref,
            name=name,
            field_type=ftype,
            is_configured=ref in configured_refs,
        ))

    discovered.sort(key=lambda d: (not d.is_configured, d.name.lower()))
    return discovered


# ── List ──────────────────────────────────────────────────────────────

@router.get("", response_model=list[CustomFieldConfigOut])
async def list_custom_fields(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CustomFieldConfig)
        .where(CustomFieldConfig.project_id == project_id)
        .order_by(CustomFieldConfig.display_name)
    )
    rows = result.scalars().all()
    return [
        CustomFieldConfigOut(
            id=str(r.id),
            project_id=str(r.project_id),
            field_reference_name=r.field_reference_name,
            display_name=r.display_name,
            field_type=r.field_type,
            enabled=r.enabled,
        )
        for r in rows
    ]


# ── Bulk upsert ───────────────────────────────────────────────────────

@router.put("", response_model=list[CustomFieldConfigOut])
async def bulk_upsert_custom_fields(
    project_id: uuid.UUID,
    body: BulkUpsertRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    existing_result = await db.execute(
        select(CustomFieldConfig).where(CustomFieldConfig.project_id == project_id)
    )
    existing_map = {r.field_reference_name: r for r in existing_result.scalars().all()}

    touched: list[CustomFieldConfig] = []
    for item in body.fields:
        if item.field_reference_name in existing_map:
            row = existing_map[item.field_reference_name]
            row.display_name = item.display_name
            row.field_type = item.field_type
            row.enabled = item.enabled
        else:
            row = CustomFieldConfig(
                project_id=project_id,
                field_reference_name=item.field_reference_name,
                display_name=item.display_name,
                field_type=item.field_type,
                enabled=item.enabled,
            )
            db.add(row)
        touched.append(row)

    await db.commit()
    for r in touched:
        await db.refresh(r)

    return [
        CustomFieldConfigOut(
            id=str(r.id),
            project_id=str(r.project_id),
            field_reference_name=r.field_reference_name,
            display_name=r.display_name,
            field_type=r.field_type,
            enabled=r.enabled,
        )
        for r in touched
    ]


# ── Delete ────────────────────────────────────────────────────────────

@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_field(
    project_id: uuid.UUID,
    config_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CustomFieldConfig).where(
            CustomFieldConfig.id == config_id,
            CustomFieldConfig.project_id == project_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Custom field config not found")

    await db.delete(row)
    await db.commit()
