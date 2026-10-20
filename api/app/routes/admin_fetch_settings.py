"""/api/admin/fetch-settings — 并发 / 超时 / 分块下载。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_session
from app.models.user import User
from app.schemas.fetch_settings import FetchSettingsRead, FetchSettingsUpdate
from app.services import fetch_settings as svc

router = APIRouter(prefix="/admin/fetch-settings", tags=["admin-fetch-settings"])


@router.get("", response_model=FetchSettingsRead)
async def get_fetch_settings(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.get_fetch_settings(session)


@router.put("", response_model=FetchSettingsRead)
async def put_fetch_settings(
    body: FetchSettingsUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.update_fetch_settings(session, body)
