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
from app.db.models.user import User
from app.agent.agent import run_agent_stream

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    session_id: uuid.UUID | None = None
    message: str


class ChatSessionOut(BaseModel):
    id: uuid.UUID
    title: str
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
    ai_enabled = ai_row and ai_row.enabled and ai_row.api_key_encrypted
    if not ai_enabled:
        from app.config import settings
        if not settings.ai_api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI agent is not configured. An admin must configure it in Settings.",
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
            session = ChatSession(user_id=user.id, title=title)
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

    async def event_generator():
        collected = ""
        try:
            yield {"event": "session", "data": json.dumps({"session_id": str(session_id)})}
            async for chunk in run_agent_stream(db, body.message, chat_history):
                collected += chunk
                yield {"event": "token", "data": json.dumps({"content": chunk})}
            yield {"event": "done", "data": json.dumps({"content": collected})}
        except Exception:
            logger.exception("Agent streaming error")
            if not collected:
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
                    await db.execute(
                        update(ChatSession)
                        .where(ChatSession.id == session_id)
                        .values(updated_at=datetime.now(timezone.utc))
                    )
                    await db.commit()
                    break
                except Exception:
                    if attempt == 0:
                        logger.warning("Session may be poisoned, retrying after rollback")
                    else:
                        logger.exception("Failed to persist assistant response")

    return EventSourceResponse(event_generator())


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
    return result.scalars().all()


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
