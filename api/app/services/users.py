"""User 服务：登录、创建、状态切换、密码重置。"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ConflictError, UnauthorizedError
from app.models.user import User
from app.schemas.user import UserCreateRequest


async def authenticate(session: AsyncSession, *, phone: str, password: str) -> User:
    """校验手机号+密码。失败抛 UnauthorizedError（不区分用户是否存在，统一文案）。"""
    result = await session.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    if user is None or not user.check_password(password):
        raise UnauthorizedError("手机号或密码错误")
    if user.status != "active":
        raise UnauthorizedError("账号已停用")
    user.last_login_at = datetime.now(UTC)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_by_id(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def create_user(session: AsyncSession, body: UserCreateRequest) -> User:
    existing = await session.execute(select(User.id).where(User.phone == body.phone))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("手机号已存在")
    user = User(
        phone=body.phone,
        name=body.name,
        role=body.role,
        status="active",
    )
    user.set_password(body.password)
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("手机号已存在") from exc
    await session.refresh(user)
    return user


async def list_users(
    session: AsyncSession,
    *,
    search: str | None,
    page: int,
    size: int,
) -> tuple[list[User], int]:
    stmt = select(User)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(User.phone.like(like) | User.name.like(like))
    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    stmt = stmt.order_by(User.id.desc()).offset((page - 1) * size).limit(size)
    items = (await session.execute(stmt)).scalars().all()
    return list(items), int(total or 0)


async def reset_password(session: AsyncSession, user: User, *, new_password: str) -> None:
    if len(new_password) < 8:
        raise BadRequestError("密码至少 8 位")
    user.set_password(new_password)
    session.add(user)
    await session.commit()


async def set_status(session: AsyncSession, user: User, *, status: str) -> None:
    if status not in ("active", "disabled"):
        raise BadRequestError("status 取值必须是 active 或 disabled")
    user.status = status
    session.add(user)
    await session.commit()
