"""DefaultModels service: which model_id each role uses.

roles: chat / tts / stt / logo / embedding / cover_image.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, NotFoundError
from app.models.default_model import DEFAULT_MODEL_ROLES, DefaultModel


def _to_dict(d: DefaultModel) -> dict:
    return {
        "id": d.id,
        "role": d.role,
        "model_id": d.model_id,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }


async def list_default_models(session: AsyncSession) -> list[dict]:
    items = (await session.execute(select(DefaultModel))).scalars().all()
    by_role = {d.role: d.model_id for d in items}
    return [
        {
            "role": role,
            "model_id": by_role.get(role),
            "default_model_role": role,
        }
        for role in DEFAULT_MODEL_ROLES
    ]


async def get_default_model_id(session: AsyncSession, role: str) -> int | None:
    if role not in DEFAULT_MODEL_ROLES:
        raise BadRequestError(f"unknown role: {role}; allowed={list(DEFAULT_MODEL_ROLES)}")
    d = (
        await session.execute(select(DefaultModel).where(DefaultModel.role == role))
    ).scalar_one_or_none()
    return d.model_id if d else None


async def set_default_model(
    session: AsyncSession,
    role: str,
    model_id: int,
) -> dict:
    if role not in DEFAULT_MODEL_ROLES:
        raise BadRequestError(f"unknown role: {role}")
    existing = (
        await session.execute(select(DefaultModel).where(DefaultModel.role == role))
    ).scalar_one_or_none()
    if existing is None:
        d = DefaultModel(role=role, model_id=model_id)
        session.add(d)
    else:
        existing.model_id = model_id
        session.add(existing)
        d = existing
    await session.commit()
    await session.refresh(d)
    return _to_dict(d)


async def clear_default_model(session: AsyncSession, role: str) -> None:
    if role not in DEFAULT_MODEL_ROLES:
        raise BadRequestError(f"unknown role: {role}")
    d = (
        await session.execute(select(DefaultModel).where(DefaultModel.role == role))
    ).scalar_one_or_none()
    if d is None:
        raise NotFoundError(f"role={role} is not set")
    await session.delete(d)
    await session.commit()
