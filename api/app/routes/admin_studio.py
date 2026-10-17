"""/api/admin/studio — 产物格式列表与能力管理。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_session
from app.models.user import User
from app.schemas.studio import CapabilityRead, CapabilityUpdate, CapabilityWrite, FormatRead
from app.services import capabilities as svc
from app.studio.formats import list_formats

router = APIRouter(prefix="/admin/studio", tags=["admin-studio"])


@router.get("/formats", response_model=list[FormatRead])
async def list_studio_formats(_: User = Depends(require_admin)):
    return [{"key": fmt.key, "label": fmt.label} for fmt in list_formats()]


@router.get("/capabilities", response_model=list[CapabilityRead])
async def list_capabilities(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.list_capabilities(session)


@router.post("/capabilities", response_model=CapabilityRead, status_code=status.HTTP_201_CREATED)
async def create_capability(
    body: CapabilityWrite,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.create_capability(
        session,
        name=body.name,
        icon=body.icon,
        format_key=body.format_key,
        agent_id=body.agent_id,
        form=body.form,
    )


@router.get("/capabilities/{capability_id}", response_model=CapabilityRead)
async def get_capability(
    capability_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.get_capability(session, capability_id)


@router.patch("/capabilities/{capability_id}", response_model=CapabilityRead)
async def update_capability(
    capability_id: int,
    body: CapabilityUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.update_capability(
        session,
        capability_id,
        name=body.name,
        icon=body.icon,
        agent_id=body.agent_id,
        form=body.form,
        fields_set=body.model_fields_set,
    )


@router.post("/capabilities/{capability_id}/disable", response_model=CapabilityRead)
async def disable_capability(
    capability_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.disable_capability(session, capability_id)


@router.post("/capabilities/{capability_id}/enable", response_model=CapabilityRead)
async def enable_capability(
    capability_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.enable_capability(session, capability_id)


@router.delete("/capabilities/{capability_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_capability(
    capability_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    await svc.delete_capability(session, capability_id)
    return None
