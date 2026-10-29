"""/api/admin/draft-strategies — 底稿策略全局设置 + CRUD + 试跑。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_session
from app.models.user import User
from app.schemas.draft_strategy import (
    DraftStrategyCreate,
    DraftStrategyPlaygroundRequest,
    DraftStrategyPlaygroundResponse,
    DraftStrategyRead,
    DraftStrategySettingsRead,
    DraftStrategySettingsUpdate,
    DraftStrategyUpdate,
)
from app.services import draft_strategy as svc

router = APIRouter(prefix="/admin/draft-strategies", tags=["admin-draft-strategies"])


@router.get("/settings", response_model=DraftStrategySettingsRead)
async def get_settings(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.get_settings(session)


@router.put("/settings", response_model=DraftStrategySettingsRead)
async def put_settings(
    body: DraftStrategySettingsUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.update_settings(session, body)


@router.get("", response_model=list[DraftStrategyRead])
async def list_strategies(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.list_strategies(session)


@router.post("", response_model=DraftStrategyRead)
async def create_strategy(
    body: DraftStrategyCreate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.create_strategy(session, body)


@router.get("/{strategy_id}", response_model=DraftStrategyRead)
async def get_strategy(
    strategy_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.get_strategy(session, strategy_id)


@router.put("/{strategy_id}", response_model=DraftStrategyRead)
async def update_strategy(
    strategy_id: int,
    body: DraftStrategyUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.update_strategy(session, strategy_id, body)


@router.delete("/{strategy_id}")
async def delete_strategy(
    strategy_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    await svc.delete_strategy(session, strategy_id)
    return {"ok": True}


@router.post("/playground", response_model=DraftStrategyPlaygroundResponse)
async def playground(
    body: DraftStrategyPlaygroundRequest,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.run_playground(session, body)
