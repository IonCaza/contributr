import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.db.models import User, PlatformCredential
from app.db.models.repository import Platform
from app.auth.dependencies import get_current_user
from app.services.ssh_manager import _get_fernet

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/platform-credentials", tags=["platform-credentials"])


class CredentialCreate(BaseModel):
    name: str
    platform: Platform
    token: str
    base_url: str | None = None


class CredentialResponse(BaseModel):
    id: uuid.UUID
    name: str
    platform: str
    base_url: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class CredentialTestResult(BaseModel):
    success: bool
    message: str


def _encrypt_token(token: str) -> str:
    return _get_fernet().encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    return _get_fernet().decrypt(encrypted.encode()).decode()


@router.get("", response_model=list[CredentialResponse])
async def list_credentials(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    result = await db.execute(select(PlatformCredential).order_by(PlatformCredential.name))
    return result.scalars().all()


@router.post("", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED)
async def create_credential(body: CredentialCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    cred = PlatformCredential(
        name=body.name,
        platform=body.platform,
        token_encrypted=_encrypt_token(body.token),
        base_url=body.base_url,
        created_by_id=user.id,
    )
    db.add(cred)
    await db.commit()
    await db.refresh(cred)
    return cred


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(credential_id: uuid.UUID, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    result = await db.execute(select(PlatformCredential).where(PlatformCredential.id == credential_id))
    cred = result.scalar_one_or_none()
    if cred is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")
    await db.delete(cred)
    await db.commit()


@router.post("/{credential_id}/test", response_model=CredentialTestResult)
async def test_credential(credential_id: uuid.UUID, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    result = await db.execute(select(PlatformCredential).where(PlatformCredential.id == credential_id))
    cred = result.scalar_one_or_none()
    if cred is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")

    token = decrypt_token(cred.token_encrypted)

    try:
        if cred.platform == Platform.AZURE:
            from azure.devops.connection import Connection
            from msrest.authentication import BasicAuthentication
            base_url = cred.base_url
            if not base_url:
                return CredentialTestResult(success=False, message="Base URL is required for Azure DevOps")
            conn = Connection(base_url=base_url, creds=BasicAuthentication("", token))
            core = conn.clients.get_core_client()
            projects = core.get_projects()
            return CredentialTestResult(success=True, message=f"Connected. Found {len(projects)} project(s).")

        elif cred.platform == Platform.GITHUB:
            from github import Github
            gh = Github(token)
            user_obj = gh.get_user()
            gh.close()
            return CredentialTestResult(success=True, message=f"Connected as {user_obj.login}.")

        elif cred.platform == Platform.GITLAB:
            import gitlab
            url = cred.base_url or "https://gitlab.com"
            gl = gitlab.Gitlab(url, private_token=token)
            gl.auth()
            return CredentialTestResult(success=True, message=f"Connected as {gl.user.username}.")

    except Exception as e:
        logger.warning("Platform credential test failed for %s: %s", cred.name, e)
        return CredentialTestResult(success=False, message=str(e)[:500])

    return CredentialTestResult(success=False, message="Unknown platform")


# ---------------------------------------------------------------------------
# Repository discovery
# ---------------------------------------------------------------------------

class DiscoverReposRequest(BaseModel):
    project_name: str


class DiscoveredRepo(BaseModel):
    name: str
    remote_url: str | None = None
    ssh_url: str | None = None
    default_branch: str | None = None
    web_url: str | None = None


@router.post("/{credential_id}/discover-repos", response_model=list[DiscoveredRepo])
async def discover_repos(
    credential_id: uuid.UUID,
    body: DiscoverReposRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """List repositories in an Azure DevOps project using a stored PAT."""
    result = await db.execute(
        select(PlatformCredential).where(PlatformCredential.id == credential_id)
    )
    cred = result.scalar_one_or_none()
    if cred is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")

    if cred.platform != Platform.AZURE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository discovery is only supported for Azure DevOps credentials",
        )

    if not cred.base_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credential is missing a base URL (Azure DevOps org URL)",
        )

    token = decrypt_token(cred.token_encrypted)

    try:
        from azure.devops.connection import Connection
        from msrest.authentication import BasicAuthentication

        conn = Connection(base_url=cred.base_url, creds=BasicAuthentication("", token))
        git_client = conn.clients.get_git_client()
        repos = git_client.get_repositories(body.project_name)
    except Exception as e:
        logger.warning("Repo discovery failed for credential %s: %s", cred.name, e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to discover repositories: {str(e)[:500]}",
        )

    return [
        DiscoveredRepo(
            name=r.name,
            remote_url=r.remote_url,
            ssh_url=r.ssh_url,
            default_branch=r.default_branch,
            web_url=getattr(r, "web_url", None),
        )
        for r in repos
    ]
