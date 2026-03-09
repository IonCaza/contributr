from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.auth.dependencies import get_current_user
from app.db.base import get_db
from app.db.models.chat import ChatSession, ChatMessage, MessageRole
from app.db.models.ai_settings import AiSettings, SINGLETON_ID
from app.db.models.agent_config import AgentConfig
from app.db.models.user import User
from app.agents.runner import run_agent_stream

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    session_id: uuid.UUID | None = None
    message: str
    agent_slug: str = "contribution-analyst"


class ChatSessionOut(BaseModel):
    id: uuid.UUID
    title: str
    agent_slug: str | None = None
    archived_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


@router.post("")
async def send_message(
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ai_row = (await db.execute(select(AiSettings).where(AiSettings.id == SINGLETON_ID))).scalar_one_or_none()
    if not (ai_row and ai_row.enabled):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI is not enabled. An admin must enable it in Settings > AI.",
        )

    agent_row = (await db.execute(
        select(AgentConfig).where(AgentConfig.slug == body.agent_slug, AgentConfig.enabled.is_(True))
    )).scalar_one_or_none()
    if not agent_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{body.agent_slug}' not found or not enabled.",
        )

    try:
        if body.session_id:
            result = await db.execute(
                select(ChatSession).where(
                    ChatSession.id == body.session_id,
                    ChatSession.user_id == user.id,
                )
            )
            session = result.scalar_one_or_none()
            if not session:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        else:
            title = body.message[:100].strip() or "New chat"
            session = ChatSession(user_id=user.id, title=title, agent_id=agent_row.id)
            db.add(session)
            await db.flush()

        user_msg = ChatMessage(
            session_id=session.id,
            role=MessageRole.USER,
            content=body.message,
        )
        db.add(user_msg)
        session_id = session.id
        user_msg_id = user_msg.id
        await db.commit()
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to persist chat message")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process chat message.",
        )

    session_row = (await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )).scalar_one()
    existing_summary = session_row.context_summary

    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    history_rows = history_result.scalars().all()
    chat_history = [
        {"role": m.role.value, "content": m.content}
        for m in history_rows
        if m.id != user_msg_id
    ]

    context_state: dict = {}

    async def event_generator():
        collected = ""
        try:
            yield {"event": "session", "data": json.dumps({"session_id": str(session_id)})}
            async for chunk in run_agent_stream(
                db, body.message, chat_history,
                agent_slug=body.agent_slug,
                session_id=session_id,
                session_summary=existing_summary,
                context_state=context_state,
            ):
                collected += chunk
                yield {"event": "token", "data": json.dumps({"content": chunk})}
            yield {"event": "done", "data": json.dumps({"content": collected})}
        except Exception as exc:
            logger.exception("Agent streaming error")
            if not collected:
                exc_str = str(exc).lower()
                if "rate" in exc_str and "limit" in exc_str:
                    collected = (
                        "The AI provider is temporarily rate-limited. "
                        "Please wait a moment and try again."
                    )
                else:
                    collected = "Sorry, I encountered an error processing your request."
                yield {"event": "error", "data": json.dumps({"detail": collected})}
        finally:
            content = collected or "No response generated."
            for attempt in range(2):
                try:
                    if attempt > 0:
                        await db.rollback()
                    assistant_msg = ChatMessage(
                        session_id=session_id,
                        role=MessageRole.ASSISTANT,
                        content=content,
                    )
                    db.add(assistant_msg)
                    update_values: dict = {"updated_at": datetime.now(timezone.utc)}
                    if "new_summary" in context_state:
                        update_values["context_summary"] = context_state["new_summary"]
                    await db.execute(
                        update(ChatSession)
                        .where(ChatSession.id == session_id)
                        .values(**update_values)
                    )
                    await db.commit()
                    break
                except Exception:
                    if attempt == 0:
                        logger.warning("Session may be poisoned, retrying after rollback")
                    else:
                        logger.exception("Failed to persist assistant response")

    return EventSourceResponse(event_generator())


class RenameRequest(BaseModel):
    title: str


def _session_out(s: ChatSession) -> ChatSessionOut:
    return ChatSessionOut(
        id=s.id,
        title=s.title,
        agent_slug=None,
        archived_at=s.archived_at,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


@router.post("/sessions", response_model=ChatSessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = ChatSession(user_id=user.id, title="New chat")
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return _session_out(session)


@router.patch("/sessions/{session_id}", response_model=ChatSessionOut)
async def rename_session(
    session_id: uuid.UUID,
    body: RenameRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    session.title = body.title
    session.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)
    return _session_out(session)


@router.get("/sessions", response_model=list[ChatSessionOut])
async def list_sessions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
    )
    sessions = result.scalars().all()
    return [_session_out(s) for s in sessions]


@router.get("/sessions/{session_id}", response_model=list[ChatMessageOut])
async def get_session_messages(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    msgs = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    return msgs.scalars().all()


@router.post("/sessions/{session_id}/archive", response_model=ChatSessionOut)
async def archive_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    session.archived_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)
    return _session_out(session)


@router.post("/sessions/{session_id}/unarchive", response_model=ChatSessionOut)
async def unarchive_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    session.archived_at = None
    await db.commit()
    await db.refresh(session)
    return _session_out(session)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    await db.delete(session)
    await db.commit()
