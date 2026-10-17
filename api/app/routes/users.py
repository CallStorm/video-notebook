"""/api/users/me — 当前登录用户的信息与改密。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.auth import UserBrief
from app.schemas.user import ChangePasswordRequest, UpdateMeRequest
from app.services.users import authenticate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserBrief)
async def get_me(user: User = Depends(get_current_active_user)) -> UserBrief:
    return UserBrief.model_validate(
        {"id": user.id, "phone": user.phone, "name": user.name, "role": user.role}
    )


@router.patch("/me", response_model=UserBrief)
async def patch_me(
    body: UpdateMeRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
) -> UserBrief:
    if body.name is not None:
        user.name = body.name
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return UserBrief.model_validate(
        {"id": user.id, "phone": user.phone, "name": user.name, "role": user.role}
    )


@router.post("/me/change_password", status_code=204)
async def change_password(
    body: ChangePasswordRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
) -> None:
    # 用 authenticate 校验旧密码（统一走 hash 路径，避免重复逻辑）
    await authenticate(session, phone=user.phone, password=body.old_password)
    user.set_password(body.new_password)
    session.add(user)
    await session.commit()
