"""/api/admin/fetch-network — Cookie + 代理。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.core.errors import BadRequestError
from app.db.session import get_session
from app.fetch_network.types import PLATFORMS, PlatformKey
from app.models.user import User
from app.schemas.fetch_network import (
    FetchNetworkRead,
    PlatformCookieUpdate,
    ProxyTestResult,
    ProxyUpdate,
)
from app.services import fetch_network as svc

router = APIRouter(prefix="/admin/fetch-network", tags=["admin-fetch-network"])


def _platform(value: str) -> PlatformKey:
    if value not in PLATFORMS:
        raise BadRequestError(f"不支持的平台: {value}")
    return value  # type: ignore[return-value]


@router.get("", response_model=FetchNetworkRead)
async def get_fetch_network(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.get_fetch_network(session)


@router.put("/cookies/{platform}", response_model=FetchNetworkRead)
async def put_platform_cookie(
    platform: str,
    body: PlatformCookieUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.update_platform_cookie(session, _platform(platform), body)


@router.delete("/cookies/{platform}", response_model=FetchNetworkRead)
async def delete_platform_cookie(
    platform: str,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.delete_platform_cookie(session, _platform(platform))


@router.put("/proxy", response_model=FetchNetworkRead)
async def put_proxy(
    body: ProxyUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.update_proxy(session, body)


@router.delete("/proxy", response_model=FetchNetworkRead)
async def delete_proxy(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.clear_proxy(session)


@router.post("/proxy/test", response_model=ProxyTestResult)
async def post_proxy_test(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.test_proxy(session)
