"""Credentials 服务：CRUD + 测试。

api_key_enc 永远不外露，给 admin 看的是 credential.mask() 的前 4 位。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, NotFoundError
from app.llm.provider_registry import (
    ProviderSpec,
    assert_provider_exists,
)
from app.models.credential import Credential


def _materialize(spec: ProviderSpec, credential: Credential) -> dict:
    """admin GET 一个 credential 的 dict 形态（不含密文）。"""
    api_key = credential.get_api_key()
    return {
        "id": credential.id,
        "name": credential.name,
        "provider": credential.provider,
        "modalities": credential.modalities_json,
        "base_url": credential.base_url,
        "config": credential.config,
        "api_key_masked": credential.mask(),
        "is_builtin": credential.is_builtin,
        "has_api_key": bool(api_key),
        "updated_at": credential.updated_at.isoformat() if credential.updated_at else None,
    }


async def list_credentials(
    session: AsyncSession,
    *,
    provider: str | None = None,
) -> list[Credential]:
    stmt = select(Credential).order_by(Credential.provider, Credential.id)
    if provider:
        stmt = stmt.where(Credential.provider == provider)
    return list((await session.execute(stmt)).scalars().all())


async def get_credential(session: AsyncSession, credential_id: int) -> Credential:
    cred = await session.get(Credential, credential_id)
    if cred is None:
        raise NotFoundError(f"credential {credential_id} 不存在")
    return cred


async def create_credential(
    session: AsyncSession,
    *,
    name: str,
    provider: str,
    api_key: str,
    modalities: list[str] | None = None,
    base_url: str | None = None,
    config: dict | None = None,
) -> dict:
    spec = assert_provider_exists(provider)
    mods = modalities or list(spec.modalities)
    # 校验 modalities 是 provider 支持的
    for m in mods:
        if m not in spec.modalities:
            raise BadRequestError(
                f"provider={spec.name} 不支持 modality={m}; 可选={list(spec.modalities)}"
            )

    cred = Credential(
        name=name,
        provider=spec.name,
        modalities_json=mods,
        base_url=base_url or spec.default_base_url,
        config=config,
        is_builtin=False,
    )
    cred.set_api_key(api_key)
    session.add(cred)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise BadRequestError("创建凭证失败：违反唯一约束") from exc
    await session.refresh(cred)
    return _materialize(spec, cred)


async def update_credential(
    session: AsyncSession,
    credential_id: int,
    *,
    name: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    config: dict | None = None,
    modalities: list[str] | None = None,
    updated_by_user_id: int | None = None,
) -> dict:
    cred = await get_credential(session, credential_id)
    spec = assert_provider_exists(cred.provider)
    if name is not None:
        cred.name = name
    if api_key:
        cred.set_api_key(api_key)
    if base_url is not None:
        cred.base_url = base_url
    if config is not None:
        cred.config = config
    if modalities is not None:
        for m in modalities:
            if m not in spec.modalities:
                raise BadRequestError(f"modality={m} 不被 {spec.name} 支持")
        cred.modalities_json = modalities
    if updated_by_user_id is not None:
        cred.updated_by_user_id = updated_by_user_id
    session.add(cred)
    await session.commit()
    await session.refresh(cred)
    return _materialize(spec, cred)


async def delete_credential(session: AsyncSession, credential_id: int) -> None:
    cred = await get_credential(session, credential_id)
    if cred.is_builtin:
        raise BadRequestError("内置凭证不可删")
    await session.delete(cred)
    await session.commit()


async def materialize_credential(session: AsyncSession, credential_id: int) -> dict:
    cred = await get_credential(session, credential_id)
    spec = assert_provider_exists(cred.provider)
    return _materialize(spec, cred)
