"""FastAPI 依赖注入：当前用户、当前 admin、当前活跃账号。"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.db.session import get_session
from app.models.user import User

_bearer = HTTPBearer(auto_error=False, description="JWT access token")


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Missing Bearer token")
    payload = decode_token(credentials.credentials, expected_type="access")
    sub = payload.get("sub")
    if not sub:
        raise UnauthorizedError("Invalid token: no subject")
    try:
        user_id = int(sub)
    except (TypeError, ValueError) as exc:
        raise UnauthorizedError("Invalid token subject") from exc

    user = await session.get(User, user_id)
    if user is None:
        raise UnauthorizedError("User not found")
    return user


async def get_current_active_user(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    if user.status != "active":
        raise ForbiddenError("用户已停用")
    return user


async def require_admin(
    user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    if user.role != "admin":
        raise ForbiddenError("需要 admin 权限")
    return user
