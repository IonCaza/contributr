from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.db.models.user import User

import app.agents.tools.contribution_analytics  # noqa: F401 — registers tools
from app.agents.tools.registry import get_all_definitions

router = APIRouter(prefix="/ai/tools", tags=["ai"])


class ToolDefinitionOut(BaseModel):
    slug: str
    name: str
    description: str
    category: str


@router.get("", response_model=list[ToolDefinitionOut])
async def list_tools(
    _user: User = Depends(get_current_user),
):
    return [
        ToolDefinitionOut(
            slug=d.slug,
            name=d.name,
            description=d.description,
            category=d.category,
        )
        for d in get_all_definitions()
    ]
