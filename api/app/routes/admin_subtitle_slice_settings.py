"""/api/admin/subtitle-slice-settings — ASR 语音切片参数。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_session
from app.models.user import User
from app.schemas.subtitle_slice_settings import (
    SubtitleSliceSettingsRead,
    SubtitleSliceSettingsUpdate,
)
from app.services import subtitle_slice_settings as svc

router = APIRouter(
    prefix="/admin/subtitle-slice-settings", tags=["admin-subtitle-slice-settings"]
)


@router.get("", response_model=SubtitleSliceSettingsRead)
async def get_subtitle_slice_settings(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.get_subtitle_slice_settings(session)


@router.put("", response_model=SubtitleSliceSettingsRead)
async def put_subtitle_slice_settings(
    body: SubtitleSliceSettingsUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.update_subtitle_slice_settings(session, body)
