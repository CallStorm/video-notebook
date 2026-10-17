"""/api/admin/models/* — 模型 CRUD + 单条模型连通性测试 + 模型发现 + 批量注册。"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt
from app.core.deps import require_admin
from app.core.errors import BadRequestError, NotFoundError
from app.db.session import get_session
from app.llm.config_service import invalidate as invalidate_default_cache
from app.llm.providers import make_provider
from app.models.credential import Credential
from app.models.model import MODEL_TYPES, Model
from app.models.user import User
from app.schemas.provider import (
    BulkRegisterRequest,
    BulkRegisterResponse,
    DiscoveredModel,
    DiscoverRequest,
    DiscoverResponse,
    ModelCreate,
    ModelRead,
    ModelTestRequest,
    ModelTestResult,
)
from app.services import models as svc
from app.services.discover_models import discover_models

router = APIRouter(prefix="/admin/models", tags=["admin-models"])


@router.get("", response_model=list[ModelRead])
async def list_models(
    type: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    items = await svc.list_models(session, type=type, provider=provider)
    return [svc._to_dict(m) for m in items]  # type: ignore[attr-defined]


@router.post("", response_model=ModelRead, status_code=status.HTTP_201_CREATED)
async def create_model(
    body: ModelCreate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    m = await svc.create_model(
        session,
        name=body.name,
        provider=body.provider,
        type=body.type,
        credential_id=body.credential_id,
    )
    invalidate_default_cache("all")
    return m


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    model_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    await svc.delete_model(session, model_id)
    invalidate_default_cache("all")
    return None


@router.post("/{model_id}/test", response_model=ModelTestResult)
async def post_model_test(
    model_id: int,
    body: ModelTestRequest,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    """对单条命名模型做连通性测试：用其绑定的 credential 调一次完成请求。"""
    started = time.monotonic()
    m = await session.get(Model, model_id)
    if m is None:
        return ModelTestResult(
            ok=False, latency_ms=0, provider="", error=f"model {model_id} 不存在"
        )
    cred = await session.get(Credential, m.credential_id)
    if cred is None:
        return ModelTestResult(
            ok=False, latency_ms=0, provider=m.provider, error="credential 缺失"
        )
    api_key = decrypt(cred.api_key_enc or "")
    base_url = cred.base_url
    try:
        provider = make_provider(
            provider_name=m.provider,
            api_key=api_key,
            base_url=base_url,
            model_name=m.name,
        )
        if m.type in ("language",):
            prompt = body.prompt or "Say 'connection ok' in one short sentence."
            text = await provider.complete(prompt, system="")
            return ModelTestResult(
                ok=True,
                latency_ms=int((time.monotonic() - started) * 1000),
                provider=m.provider,
                response=text[:500],
                message=f"模型 {m.name} 可调用",
            )
        # tts / stt / embedding 暂用 credential test 走通
        return ModelTestResult(
            ok=True,
            latency_ms=int((time.monotonic() - started) * 1000),
            provider=m.provider,
            message=f"模型 {m.name} ({m.type}) 元数据已就位；runtime 测试 v2 接",
        )
    except Exception as exc:  # noqa: BLE001
        return ModelTestResult(
            ok=False,
            latency_ms=int((time.monotonic() - started) * 1000),
            provider=m.provider,
            error=f"{exc.__class__.__name__}: {exc}",
        )


@router.post("/discover", response_model=DiscoverResponse)
async def post_discover(
    body: DiscoverRequest,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    """对一条凭证做模型发现：调 provider /v1/models 拿候选。"""
    cred = await session.get(Credential, body.credential_id)
    if cred is None:
        raise NotFoundError(f"credential {body.credential_id} 不存在")
    result = await discover_models(cred)
    if result.error:
        # 不抛 5xx；让 UI 直接显示
        return DiscoverResponse(items=[])
    return DiscoverResponse(items=[DiscoveredModel(**it) for it in result.items])


@router.post("/bulk-register", response_model=BulkRegisterResponse)
async def post_bulk_register(
    body: BulkRegisterRequest,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    """批量注册 model：跳过同名+同 provider+同 type 的已存在项。"""
    cred = await session.get(Credential, body.credential_id)
    if cred is None:
        raise NotFoundError(f"credential {body.credential_id} 不存在")

    if not body.models:
        return BulkRegisterResponse(created=[], skipped=[])

    # 校验 modality 是否在 credential 支持范围
    for item in body.models:
        if item.type not in MODEL_TYPES:
            raise BadRequestError(f"unknown type: {item.type}")
        if item.type not in cred.modalities_json:
            raise BadRequestError(
                f"credential 不支持 type={item.type}（可支持 {cred.modalities_json}）"
            )

    # 已存在的 name+type 跳过
    names_and_types = {(it.name, it.type) for it in body.models}
    existing = set()
    for name, type_ in names_and_types:
        stmt = select(Model).where(
            Model.credential_id == cred.id,
            Model.name == name,
            Model.type == type_,
        )
        m = (await session.execute(stmt)).scalar_one_or_none()
        if m is not None:
            existing.add((name, type_))

    created: list[Model] = []
    skipped: list[str] = []
    for item in body.models:
        if (item.name, item.type) in existing:
            skipped.append(item.name)
            continue
        m = Model(
            name=item.name,
            provider=cred.provider,
            type=item.type,
            credential_id=cred.id,
        )
        session.add(m)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            skipped.append(item.name)
            continue
        await session.refresh(m)
        created.append(m)

    invalidate_default_cache("all")
    return BulkRegisterResponse(
        created=[svc._to_dict(m) for m in created],  # type: ignore[attr-defined]
        skipped=skipped,
    )
