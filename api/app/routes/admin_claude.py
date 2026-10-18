"""/api/admin/claude-code — 全站 Claude Code 连接配置。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_session
from app.models.user import User
from app.schemas.studio import ClaudeCodeRead, ClaudeCodeUpdate
from app.services import claude_config as svc

router = APIRouter(prefix="/admin/claude-code", tags=["admin-claude"])


@router.get("", response_model=ClaudeCodeRead)
async def get_claude_code(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.get_claude_config(session)


@router.put("", response_model=ClaudeCodeRead)
async def update_claude_code(
    body: ClaudeCodeUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.update_claude_config(session, body)
