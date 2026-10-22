"""/api/admin/overview-settings — 字幕完成后自动概览与提示词。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_session
from app.models.user import User
from app.schemas.overview_settings import OverviewSettingsRead, OverviewSettingsUpdate
from app.services import overview_settings as svc

router = APIRouter(prefix="/admin/overview-settings", tags=["admin-overview-settings"])


@router.get("", response_model=OverviewSettingsRead)
async def get_overview_settings(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.get_overview_settings(session)


@router.put("", response_model=OverviewSettingsRead)
async def put_overview_settings(
    body: OverviewSettingsUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.update_overview_settings(session, body)
