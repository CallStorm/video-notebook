"""/api/admin/cover-settings — 封面生成提示词与参数。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_session
from app.models.user import User
from app.schemas.cover_settings import CoverSettingsRead, CoverSettingsUpdate
from app.services import cover_settings as svc

router = APIRouter(prefix="/admin/cover-settings", tags=["admin-cover-settings"])


@router.get("", response_model=CoverSettingsRead)
async def get_cover_settings(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.get_cover_settings(session)


@router.put("", response_model=CoverSettingsRead)
async def put_cover_settings(
    body: CoverSettingsUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.update_cover_settings(session, body)
