"""/api/admin/users — 管理员专属：用户 CRUD。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.core.errors import NotFoundError
from app.db.session import get_session
from app.models.user import User
from app.schemas.user import UserCreateRequest, UserListResponse, UserRead
from app.services.users import create_user, list_users, reset_password, set_status

router = APIRouter(prefix="/admin/users", tags=["admin"])


@router.get("", response_model=UserListResponse)
async def admin_list_users(
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
) -> UserListResponse:
    items, total = await list_users(session, search=search, page=page, size=size)
    return UserListResponse(
        items=[UserRead.model_validate(_to_read(u)) for u in items],
        total=total,
        page=page,
        size=size,
    )


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def admin_create_user(
    body: UserCreateRequest,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
) -> UserRead:
    user = await create_user(session, body)
    return UserRead.model_validate(_to_read(user))


@router.post("/{user_id}/reset_password", status_code=204)
async def admin_reset_password(
    user_id: int,
    body: dict,  # {"new_password": str}
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
) -> None:
    target = await session.get(User, user_id)
    if target is None:
        raise NotFoundError("用户不存在")
    new_password = body.get("new_password")
    if not isinstance(new_password, str):
        from app.core.errors import BadRequestError

        raise BadRequestError("缺少 new_password")
    await reset_password(session, target, new_password=new_password)


@router.post("/{user_id}/disable", status_code=204)
async def admin_disable_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
) -> None:
    target = await session.get(User, user_id)
    if target is None:
        raise NotFoundError("用户不存在")
    await set_status(session, target, status="disabled")


@router.post("/{user_id}/enable", status_code=204)
async def admin_enable_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
) -> None:
    target = await session.get(User, user_id)
    if target is None:
        raise NotFoundError("用户不存在")
    await set_status(session, target, status="active")


def _to_read(u: User) -> dict:
    return {
        "id": u.id,
        "phone": u.phone,
        "name": u.name,
        "role": u.role,
        "status": u.status,
        "created_at": u.created_at.isoformat() if u.created_at else "",
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
    }
