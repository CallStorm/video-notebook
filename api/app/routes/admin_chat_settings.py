"""/api/admin/chat-settings — 对话历史轮数。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_session
from app.models.user import User
from app.schemas.chat_settings import ChatSettingsRead, ChatSettingsUpdate
from app.services import chat_settings as svc

router = APIRouter(prefix="/admin/chat-settings", tags=["admin-chat-settings"])


@router.get("", response_model=ChatSettingsRead)
async def get_chat_settings(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.get_chat_settings(session)


@router.put("", response_model=ChatSettingsRead)
async def put_chat_settings(
    body: ChatSettingsUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.update_chat_settings(session, body)
