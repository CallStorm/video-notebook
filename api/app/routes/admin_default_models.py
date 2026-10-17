"""/api/admin/default-models — role → model_id 的双向绑定。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_session
from app.llm.config_service import invalidate as invalidate_default_cache
from app.models.default_model import DEFAULT_MODEL_ROLES
from app.models.user import User
from app.schemas.provider import DefaultModelRead, DefaultModelSet
from app.services import default_models as svc

router = APIRouter(prefix="/admin/default-models", tags=["admin-default-models"])


@router.get("", response_model=list[DefaultModelRead])
async def list_default_models(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.list_default_models(session)


@router.put("/{role}", response_model=DefaultModelRead)
async def set_default_model(
    role: str = Path(...),
    body: DefaultModelSet = ...,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    if role not in DEFAULT_MODEL_ROLES:
        from app.core.errors import BadRequestError
        raise BadRequestError(f"unknown role: {role}")
    await svc.set_default_model(session, role, body.model_id)
    invalidate_default_cache(role)
    return {"role": role, "model_id": body.model_id}


@router.delete("/{role}", status_code=status.HTTP_204_NO_CONTENT)
async def clear_default_model(
    role: str = Path(...),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    await svc.clear_default_model(session, role)
    invalidate_default_cache(role)
    return None
