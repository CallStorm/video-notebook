"""/api/admin/credentials/* — 凭据 CRUD + 测试。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_session
from app.llm.config_service import invalidate as invalidate_default_cache
from app.llm.connection_tester import test_credential
from app.models.user import User
from app.schemas.provider import CredentialCreate, CredentialRead, CredentialUpdate
from app.services import credentials as svc

router = APIRouter(prefix="/admin/credentials", tags=["admin-credentials"])


@router.get("", response_model=list[CredentialRead])
async def list_credentials(
    provider: str | None = None,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    creds = await svc.list_credentials(session, provider=provider)
    out: list[dict] = []
    for cred in creds:
        from app.llm.provider_registry import PROVIDERS
        spec = PROVIDERS.get(cred.provider)
        if spec is None:
            continue
        out.append(svc._materialize(spec, cred))  # type: ignore[attr-defined]
    return out


@router.post("", response_model=CredentialRead, status_code=status.HTTP_201_CREATED)
async def create_credential(
    body: CredentialCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    cred = await svc.create_credential(
        session,
        name=body.name,
        provider=body.provider,
        api_key=body.api_key,
        modalities=body.modalities,
        base_url=body.base_url,
        config=body.config,
    )
    invalidate_default_cache("all")
    return cred


@router.get("/{credential_id}", response_model=CredentialRead)
async def get_credential(
    credential_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.materialize_credential(session, credential_id)


@router.patch("/{credential_id}", response_model=CredentialRead)
async def update_credential(
    credential_id: int,
    body: CredentialUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    cred = await svc.update_credential(
        session,
        credential_id,
        name=body.name,
        api_key=body.api_key,
        base_url=body.base_url,
        config=body.config,
        modalities=body.modalities,
        updated_by_user_id=user.id,
    )
    invalidate_default_cache("all")
    return cred


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    await svc.delete_credential(session, credential_id)
    invalidate_default_cache("all")
    return None


@router.post("/{credential_id}/test")
async def post_credential_test(
    credential_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    cred = await svc.get_credential(session, credential_id)
    api_key = cred.get_api_key()
    result = await test_credential(
        cred.provider,
        api_key,
        base_url=cred.base_url,
    )
    invalidate_default_cache("all")  # 测试也触一次失效，便于立刻生效
    return result
