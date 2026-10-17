"""/api/auth/* — 登录、刷新、登出。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.db.session import get_session
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, RefreshRequest, TokenPair
from app.services.users import authenticate

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> LoginResponse:
    user = await authenticate(session, phone=body.phone, password=body.password)
    access, ttl = create_access_token(user.id, role=user.role)
    refresh = create_refresh_token(user.id)
    return LoginResponse(
        access=access,
        refresh=refresh,
        expires_in=ttl,
        user={"id": user.id, "phone": user.phone, "name": user.name, "role": user.role},
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    body: RefreshRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenPair:
    payload = decode_token(body.refresh, expected_type="refresh")
    user_id = int(payload["sub"])
    user = await session.get(User, user_id)
    if user is None or user.status != "active":
        from app.core.errors import UnauthorizedError

        raise UnauthorizedError("User unavailable")
    access, ttl = create_access_token(user.id, role=user.role)
    new_refresh = create_refresh_token(user.id)
    return TokenPair(access=access, refresh=new_refresh, expires_in=ttl)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(_user: User = Depends(get_current_active_user)) -> None:
    """v1 简化：JWT 是无状态的；登出仅由前端清掉本地 token。
    真做 refresh 撤销列表放 v2。"""
    return None
