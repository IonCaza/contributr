import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.db.models import User
from app.db.models.adr import Adr, AdrRepository, AdrTemplate, AdrStatus
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/projects/{project_id}/adrs", tags=["adrs"])


# ── Schemas ────────────────────────────────────────────────────────────

class AdrConfigResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    repository_id: uuid.UUID | None
    directory_path: str
    naming_convention: str
    next_number: int
    created_at: datetime
    updated_at: datetime | None

class AdrConfigUpdate(BaseModel):
    repository_id: uuid.UUID | None = None
    directory_path: str | None = None
    naming_convention: str | None = None

class AdrTemplateResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID | None
    name: str
    description: str | None
    content: str
    is_default: bool
    created_at: datetime
    updated_at: datetime | None

class AdrTemplateCreate(BaseModel):
    name: str
    description: str | None = None
    content: str
    is_default: bool = False

class AdrTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    content: str | None = None
    is_default: bool | None = None

class AdrResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    adr_number: int
    title: str
    slug: str
    status: str
    content: str
    template_id: uuid.UUID | None
    superseded_by_id: uuid.UUID | None
    file_path: str | None
    last_committed_sha: str | None
    pr_url: str | None
    committed_to_repo_at: datetime | None
    removed_from_repo_at: datetime | None
    location: str
    created_by_id: uuid.UUID
    created_at: datetime
    updated_at: datetime | None

class AdrCreate(BaseModel):
    title: str
    template_id: uuid.UUID | None = None
    content: str | None = None

class AdrUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    status: str | None = None
    superseded_by_id: uuid.UUID | None = None

class GenerateAdrRequest(BaseModel):
    text: str
    template_id: uuid.UUID | None = None


# ── Config ─────────────────────────────────────────────────────────────

@router.get("/config", response_model=AdrConfigResponse | None)
async def get_adr_config(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AdrRepository).where(AdrRepository.project_id == project_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        return None
    return AdrConfigResponse(
        id=config.id, project_id=config.project_id, repository_id=config.repository_id,
        directory_path=config.directory_path, naming_convention=config.naming_convention,
        next_number=config.next_number, created_at=config.created_at, updated_at=config.updated_at,
    )


@router.put("/config", response_model=AdrConfigResponse)
async def upsert_adr_config(
    project_id: uuid.UUID,
    body: AdrConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AdrRepository).where(AdrRepository.project_id == project_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        config = AdrRepository(project_id=project_id)
        db.add(config)

    if body.repository_id is not None:
        config.repository_id = body.repository_id
    if body.directory_path is not None:
        config.directory_path = body.directory_path
    if body.naming_convention is not None:
        config.naming_convention = body.naming_convention
    config.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(config)
    return AdrConfigResponse(
        id=config.id, project_id=config.project_id, repository_id=config.repository_id,
        directory_path=config.directory_path, naming_convention=config.naming_convention,
        next_number=config.next_number, created_at=config.created_at, updated_at=config.updated_at,
    )


@router.post("/config/sync")
async def sync_from_repo(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    from app.services.adr_git import sync_adrs_from_repo
    count = await sync_adrs_from_repo(db, project_id)
    await db.commit()
    return {"synced": count}


# ── Templates ──────────────────────────────────────────────────────────

@router.get("/templates", response_model=list[AdrTemplateResponse])
async def list_templates(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AdrTemplate).where(
            (AdrTemplate.project_id == project_id) | (AdrTemplate.project_id.is_(None))
        ).order_by(AdrTemplate.name)
    )
    templates = result.scalars().all()
    return [
        AdrTemplateResponse(
            id=t.id, project_id=t.project_id, name=t.name, description=t.description,
            content=t.content, is_default=t.is_default, created_at=t.created_at, updated_at=t.updated_at,
        )
        for t in templates
    ]


@router.post("/templates", response_model=AdrTemplateResponse, status_code=201)
async def create_template(
    project_id: uuid.UUID,
    body: AdrTemplateCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    if body.is_default:
        await _clear_default_templates(db, project_id)

    template = AdrTemplate(
        project_id=project_id,
        name=body.name,
        description=body.description,
        content=body.content,
        is_default=body.is_default,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return AdrTemplateResponse(
        id=template.id, project_id=template.project_id, name=template.name,
        description=template.description, content=template.content,
        is_default=template.is_default, created_at=template.created_at, updated_at=template.updated_at,
    )


@router.put("/templates/{template_id}", response_model=AdrTemplateResponse)
async def update_template(
    project_id: uuid.UUID,
    template_id: uuid.UUID,
    body: AdrTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(AdrTemplate).where(AdrTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(404, "Template not found")

    if body.is_default:
        await _clear_default_templates(db, project_id)
    if body.name is not None:
        template.name = body.name
    if body.description is not None:
        template.description = body.description
    if body.content is not None:
        template.content = body.content
    if body.is_default is not None:
        template.is_default = body.is_default
    template.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(template)
    return AdrTemplateResponse(
        id=template.id, project_id=template.project_id, name=template.name,
        description=template.description, content=template.content,
        is_default=template.is_default, created_at=template.created_at, updated_at=template.updated_at,
    )


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template(
    project_id: uuid.UUID,
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(AdrTemplate).where(AdrTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(404, "Template not found")
    await db.delete(template)
    await db.commit()


async def _clear_default_templates(db: AsyncSession, project_id: uuid.UUID):
    result = await db.execute(
        select(AdrTemplate).where(
            ((AdrTemplate.project_id == project_id) | (AdrTemplate.project_id.is_(None)))
            & (AdrTemplate.is_default == True)
        )
    )
    for t in result.scalars().all():
        t.is_default = False


# ── ADRs CRUD ──────────────────────────────────────────────────────────

def _fix_azure_pr_url(url: str | None) -> str | None:
    """Fix legacy Azure DevOps PR URLs that have the org name duplicated."""
    if not url or "dev.azure.com" not in url:
        return url
    m = re.match(r"(https://dev\.azure\.com/([^/]+))/\2/(.+)", url)
    if m:
        return f"{m.group(1)}/{m.group(3)}"
    return url


def _extract_title_from_content(content: str) -> str | None:
    m = re.match(r"^#\s+(.+)$", content, re.MULTILINE)
    return m.group(1).strip() if m else None


def _adr_location(a: Adr) -> str:
    if not a.committed_to_repo_at:
        return "draft"
    if a.removed_from_repo_at:
        return "removed_from_repo"
    return "in_repo"


def _adr_to_response(a: Adr) -> AdrResponse:
    return AdrResponse(
        id=a.id, project_id=a.project_id, adr_number=a.adr_number,
        title=a.title, slug=a.slug, status=a.status.value,
        content=a.content, template_id=a.template_id,
        superseded_by_id=a.superseded_by_id, file_path=a.file_path,
        last_committed_sha=a.last_committed_sha, pr_url=_fix_azure_pr_url(a.pr_url),
        committed_to_repo_at=a.committed_to_repo_at,
        removed_from_repo_at=a.removed_from_repo_at,
        location=_adr_location(a),
        created_by_id=a.created_by_id, created_at=a.created_at, updated_at=a.updated_at,
    )


@router.get("", response_model=list[AdrResponse])
async def list_adrs(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
    status: str | None = Query(None),
    search: str | None = Query(None),
    sort_by: str = Query("adr_number"),
):
    q = select(Adr).where(Adr.project_id == project_id)
    if status:
        try:
            q = q.where(Adr.status == AdrStatus(status))
        except ValueError:
            pass
    if search:
        q = q.where(Adr.title.ilike(f"%{search}%"))

    sort_col = {
        "adr_number": Adr.adr_number,
        "title": Adr.title,
        "status": Adr.status,
        "created_at": Adr.created_at,
    }.get(sort_by, Adr.adr_number)
    q = q.order_by(sort_col)

    result = await db.execute(q)
    return [_adr_to_response(a) for a in result.scalars().all()]


@router.post("", response_model=AdrResponse, status_code=201)
async def create_adr(
    project_id: uuid.UUID,
    body: AdrCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    config_result = await db.execute(
        select(AdrRepository).where(AdrRepository.project_id == project_id)
    )
    config = config_result.scalar_one_or_none()

    adr_number = config.next_number if config else 1
    if config:
        config.next_number += 1

    content = body.content or ""
    if not content and body.template_id:
        tmpl_result = await db.execute(select(AdrTemplate).where(AdrTemplate.id == body.template_id))
        tmpl = tmpl_result.scalar_one_or_none()
        if tmpl:
            content = tmpl.content

    adr = Adr(
        project_id=project_id,
        adr_number=adr_number,
        title=body.title,
        slug=Adr.make_slug(body.title),
        content=content,
        template_id=body.template_id,
        created_by_id=user.id,
    )
    db.add(adr)
    await db.commit()
    await db.refresh(adr)
    return _adr_to_response(adr)


@router.get("/{adr_id}", response_model=AdrResponse)
async def get_adr(
    project_id: uuid.UUID,
    adr_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Adr).where(Adr.id == adr_id, Adr.project_id == project_id))
    adr = result.scalar_one_or_none()
    if not adr:
        raise HTTPException(404, "ADR not found")
    return _adr_to_response(adr)


_ALLOWED_TRANSITIONS: dict[AdrStatus, list[AdrStatus]] = {
    AdrStatus.PROPOSED: [AdrStatus.ACCEPTED, AdrStatus.REJECTED],
    AdrStatus.ACCEPTED: [AdrStatus.DEPRECATED, AdrStatus.SUPERSEDED],
    AdrStatus.DEPRECATED: [],
    AdrStatus.SUPERSEDED: [],
    AdrStatus.REJECTED: [],
}


@router.put("/{adr_id}", response_model=AdrResponse)
async def update_adr(
    project_id: uuid.UUID,
    adr_id: uuid.UUID,
    body: AdrUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Adr).where(Adr.id == adr_id, Adr.project_id == project_id))
    adr = result.scalar_one_or_none()
    if not adr:
        raise HTTPException(404, "ADR not found")

    if body.content is not None:
        adr.content = body.content
        extracted = _extract_title_from_content(body.content)
        if extracted:
            adr.title = extracted
            adr.slug = Adr.make_slug(extracted)
    elif body.title is not None:
        adr.title = body.title
        adr.slug = Adr.make_slug(body.title)

    if body.status is not None:
        try:
            new_status = AdrStatus(body.status)
        except ValueError:
            raise HTTPException(400, f"Invalid status: {body.status}")

        if new_status != adr.status:
            allowed = list(_ALLOWED_TRANSITIONS.get(adr.status, []))
            location = _adr_location(adr)
            if adr.status == AdrStatus.PROPOSED and new_status == AdrStatus.REJECTED:
                if location in ("in_repo", "removed_from_repo"):
                    raise HTTPException(
                        400,
                        "Cannot reject an ADR that has been in the repository. "
                        "Use deprecated or superseded instead.",
                    )
            if new_status not in allowed:
                raise HTTPException(
                    400,
                    f"Cannot change status from '{adr.status.value}' to '{new_status.value}'. "
                    f"Allowed transitions: {', '.join(s.value for s in allowed) or 'none (terminal state)'}.",
                )

            if new_status == AdrStatus.SUPERSEDED:
                if not body.superseded_by_id:
                    raise HTTPException(400, "superseded_by_id is required when setting status to superseded.")
                target = await db.execute(
                    select(Adr).where(Adr.id == body.superseded_by_id, Adr.project_id == project_id)
                )
                if not target.scalar_one_or_none():
                    raise HTTPException(400, "The superseding ADR was not found in this project.")
                adr.superseded_by_id = body.superseded_by_id

            adr.status = new_status

    adr.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(adr)
    return _adr_to_response(adr)


@router.delete("/{adr_id}", status_code=204)
async def delete_adr(
    project_id: uuid.UUID,
    adr_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Adr).where(Adr.id == adr_id, Adr.project_id == project_id))
    adr = result.scalar_one_or_none()
    if not adr:
        raise HTTPException(404, "ADR not found")
    await db.delete(adr)
    await db.commit()


# ── Workflow ───────────────────────────────────────────────────────────

@router.post("/{adr_id}/commit")
async def commit_adr(
    project_id: uuid.UUID,
    adr_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Adr).where(Adr.id == adr_id, Adr.project_id == project_id))
    adr = result.scalar_one_or_none()
    if not adr:
        raise HTTPException(404, "ADR not found")

    from app.services.adr_git import write_adr_to_repo
    try:
        branch, sha = await write_adr_to_repo(db, adr)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    await db.commit()
    return {"branch": branch, "sha": sha}


@router.post("/{adr_id}/pr")
async def create_pr(
    project_id: uuid.UUID,
    adr_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Adr).where(Adr.id == adr_id, Adr.project_id == project_id))
    adr = result.scalar_one_or_none()
    if not adr:
        raise HTTPException(404, "ADR not found")

    if not adr.last_committed_sha:
        raise HTTPException(400, "ADR must be committed before creating a PR. Click 'Commit' first.")

    from app.services.adr_git import create_adr_pr
    branch = f"adr/{adr.adr_number}-{adr.slug}"
    try:
        pr_url = await create_adr_pr(db, adr, branch)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    await db.commit()
    return {"pr_url": pr_url}


@router.post("/{adr_id}/merge")
async def merge_pr(
    project_id: uuid.UUID,
    adr_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(Adr).where(Adr.id == adr_id, Adr.project_id == project_id))
    adr = result.scalar_one_or_none()
    if not adr:
        raise HTTPException(404, "ADR not found")

    if not adr.pr_url:
        raise HTTPException(400, "No PR exists for this ADR. Click 'Create PR' first.")

    from app.services.adr_git import merge_adr_pr
    try:
        merged = await merge_adr_pr(db, adr)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    await db.commit()
    return {"merged": merged}


@router.post("/{adr_id}/supersede", response_model=AdrResponse)
async def supersede_adr(
    project_id: uuid.UUID,
    adr_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
    new_adr_id: uuid.UUID = Query(..., description="ID of the ADR that supersedes this one"),
):
    result = await db.execute(select(Adr).where(Adr.id == adr_id, Adr.project_id == project_id))
    adr = result.scalar_one_or_none()
    if not adr:
        raise HTTPException(404, "ADR not found")

    if adr.status != AdrStatus.ACCEPTED:
        raise HTTPException(400, f"Only accepted ADRs can be superseded (current: {adr.status.value}).")

    target = await db.execute(
        select(Adr).where(Adr.id == new_adr_id, Adr.project_id == project_id)
    )
    if not target.scalar_one_or_none():
        raise HTTPException(400, "The superseding ADR was not found in this project.")

    adr.status = AdrStatus.SUPERSEDED
    adr.superseded_by_id = new_adr_id
    adr.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(adr)
    return _adr_to_response(adr)


# ── AI Generation ─────────────────────────────────────────────────────

@router.post("/generate", response_model=AdrResponse)
async def generate_adr(
    project_id: uuid.UUID,
    body: GenerateAdrRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    template_content = ""
    if body.template_id:
        tmpl_result = await db.execute(select(AdrTemplate).where(AdrTemplate.id == body.template_id))
        tmpl = tmpl_result.scalar_one_or_none()
        if tmpl:
            template_content = tmpl.content
    else:
        tmpl_result = await db.execute(
            select(AdrTemplate).where(
                ((AdrTemplate.project_id == project_id) | (AdrTemplate.project_id.is_(None)))
                & (AdrTemplate.is_default == True)
            ).limit(1)
        )
        tmpl = tmpl_result.scalar_one_or_none()
        if tmpl:
            template_content = tmpl.content

    from app.agents.tools.adr_tools import get_adr_llm_provider
    from app.agents.llm.manager import build_llm_from_provider
    provider = await get_adr_llm_provider(db)
    if not provider:
        raise HTTPException(400, "No LLM provider configured. Assign one to the ADR Architect agent or set a default provider.")

    prompt = (
        "You are an expert software architect. Generate a well-structured Architecture Decision Record (ADR) "
        "from the following input text. Use the template format provided.\n\n"
        f"Template:\n```\n{template_content}\n```\n\n"
        f"Input text:\n{body.text}\n\n"
        "Replace all template placeholders ({{...}}) with appropriate content derived from the input. "
        "Extract a clear, concise title. Return only the markdown content of the ADR, nothing else."
    )

    try:
        llm = build_llm_from_provider(provider, streaming=False)
        response = await llm.ainvoke(prompt)
        generated_content = response.content or ""
        if isinstance(generated_content, list):
            generated_content = "".join(
                c.get("text", "") if isinstance(c, dict) else str(c) for c in generated_content
            )
    except Exception as e:
        raise HTTPException(500, f"AI generation failed: {e}")

    title_line = ""
    for line in generated_content.split("\n"):
        if line.strip().startswith("# "):
            title_line = line.strip()[2:].strip()
            num_prefix = re.match(r"\d+\.\s*", title_line)
            if num_prefix:
                title_line = title_line[num_prefix.end():]
            break
    if not title_line:
        title_line = body.text[:100]

    config_result = await db.execute(
        select(AdrRepository).where(AdrRepository.project_id == project_id)
    )
    config = config_result.scalar_one_or_none()
    adr_number = config.next_number if config else 1
    if config:
        config.next_number += 1

    adr = Adr(
        project_id=project_id,
        adr_number=adr_number,
        title=title_line,
        slug=Adr.make_slug(title_line),
        content=generated_content,
        template_id=body.template_id,
        created_by_id=user.id,
    )
    db.add(adr)
    await db.commit()
    await db.refresh(adr)
    return _adr_to_response(adr)
