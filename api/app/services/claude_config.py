"""全站一份 Claude Code 连接配置。"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError
from app.models.studio import ClaudeCodeConfig
from app.schemas.studio import ClaudeCodeRead, ClaudeCodeUpdate

_ROW_ID = 1


def _read(row: ClaudeCodeConfig | None) -> ClaudeCodeRead:
    if row is None:
        return ClaudeCodeRead(api_key_set=False, base_url=None, model_name="")
    key = row.get_api_key()
    return ClaudeCodeRead(
        api_key_set=bool(key),
        base_url=row.base_url or None,
        model_name=row.model_name or "",
    )


async def get_claude_config(session: AsyncSession) -> ClaudeCodeRead:
    row = await session.get(ClaudeCodeConfig, _ROW_ID)
    return _read(row)


async def update_claude_config(
    session: AsyncSession, payload: ClaudeCodeUpdate
) -> ClaudeCodeRead:
    model_name = payload.model_name.strip()
    if not model_name:
        raise BadRequestError("模型名不能为空")
    row = await session.get(ClaudeCodeConfig, _ROW_ID)
    if row is None:
        row = ClaudeCodeConfig(id=_ROW_ID, model_name=model_name)
        session.add(row)
    row.model_name = model_name
    base_url = (payload.base_url or "").strip()
    row.base_url = base_url or None
    api_key = (payload.api_key or "").strip()
    if api_key:
        row.set_api_key(api_key)
    await session.commit()
    await session.refresh(row)
    return _read(row)
