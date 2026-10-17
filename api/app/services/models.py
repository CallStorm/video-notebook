"""Models 服务：CRUD + 按 type / provider 过滤。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, NotFoundError
from app.llm.provider_registry import assert_provider_exists
from app.models.credential import Credential
from app.models.model import MODEL_TYPES, Model


def _to_dict(m: Model) -> dict:
    return {
        "id": m.id,
        "name": m.name,
        "provider": m.provider,
        "type": m.type,
        "credential_id": m.credential_id,
        "is_default_provider": m.is_default_provider,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


async def list_models(
    session: AsyncSession,
    *,
    type: str | None = None,
    provider: str | None = None,
) -> list[Model]:
    stmt = select(Model).order_by(Model.type, Model.provider, Model.id)
    if type:
        if type not in MODEL_TYPES:
            raise BadRequestError(f"unknown model type: {type}; allowed={MODEL_TYPES}")
        stmt = stmt.where(Model.type == type)
    if provider:
        stmt = stmt.where(Model.provider == provider)
    return list((await session.execute(stmt)).scalars().all())


async def get_model(session: AsyncSession, model_id: int) -> Model:
    m = await session.get(Model, model_id)
    if m is None:
        raise NotFoundError(f"model {model_id} 不存在")
    return m


async def create_model(
    session: AsyncSession,
    *,
    name: str,
    provider: str,
    type: str,
    credential_id: int,
) -> dict:
    spec = assert_provider_exists(provider)
    if type not in MODEL_TYPES:
        raise BadRequestError(f"unknown type: {type}; allowed={MODEL_TYPES}")
    if type not in spec.modalities:
        raise BadRequestError(
            f"provider {spec.name} 不支持 type={type}; 可选={list(spec.modalities)}"
        )
    cred = await session.get(Credential, credential_id)
    if cred is None:
        raise NotFoundError(f"credential {credential_id} 不存在")
    if cred.provider != spec.name:
        raise BadRequestError("credential.provider 与 model.provider 不一致")

    m = Model(
        name=name,
        provider=spec.name,
        type=type,
        credential_id=cred.id,
        is_default_provider=True,
    )
    session.add(m)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise BadRequestError(
            f"model (provider={spec.name}, name={name}, type={type}) 已存在"
        ) from exc
    await session.refresh(m)
    return _to_dict(m)


async def delete_model(session: AsyncSession, model_id: int) -> None:
    m = await get_model(session, model_id)
    await session.delete(m)
    await session.commit()


async def materialize_model(session: AsyncSession, model_id: int) -> dict:
    m = await get_model(session, model_id)
    return _to_dict(m)
