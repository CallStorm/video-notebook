"""Admin 对话设置：历史轮数。"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.chat_settings.defaults import (
    MAX_CHAT_HISTORY_LIMIT,
    MIN_CHAT_HISTORY_LIMIT,
)
from app.core.config import get_settings
from app.models.chat_settings import ChatSettingsConfig
from app.schemas.chat_settings import ChatSettingsRead, ChatSettingsUpdate

_ROW_ID = 1


def env_default_history_limit() -> int:
    """环境变量 CHAT_HISTORY_LIMIT / Settings.chat_history_limit，夹紧到合法范围。"""
    raw = int(get_settings().chat_history_limit)
    return max(MIN_CHAT_HISTORY_LIMIT, min(MAX_CHAT_HISTORY_LIMIT, raw))


async def _ensure_row(session: AsyncSession) -> ChatSettingsConfig:
    row = await session.get(ChatSettingsConfig, _ROW_ID)
    if row is None:
        row = ChatSettingsConfig(
            id=_ROW_ID,
            history_limit=env_default_history_limit(),
        )
        session.add(row)
        await session.flush()
    return row


def _to_read(row: ChatSettingsConfig) -> ChatSettingsRead:
    return ChatSettingsRead(
        history_limit=int(row.history_limit),
        default_history_limit=env_default_history_limit(),
    )


async def get_chat_settings(session: AsyncSession) -> ChatSettingsRead:
    row = await _ensure_row(session)
    return _to_read(row)


async def get_history_limit(session: AsyncSession) -> int:
    """供 chat service 读取生效的 N。"""
    row = await _ensure_row(session)
    n = int(row.history_limit)
    return max(MIN_CHAT_HISTORY_LIMIT, min(MAX_CHAT_HISTORY_LIMIT, n))


async def update_chat_settings(
    session: AsyncSession, body: ChatSettingsUpdate
) -> ChatSettingsRead:
    row = await _ensure_row(session)
    row.history_limit = int(body.history_limit)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _to_read(row)
