"""GET /api/admin/stats — 运营总览大屏。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_session
from app.models.user import User
from app.schemas.admin_stats import AdminStatsResponse
from app.services import admin_stats as svc

router = APIRouter(prefix="/admin", tags=["admin-stats"])


@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
) -> AdminStatsResponse:
    return await svc.get_admin_stats(session)
