"""首个管理员 seed：DB 内无 admin 时按 env 创建一个。

Phase 2 起实装：
- 检测 DB 是否已有 admin；
- 没有则用 bcrypt 哈希密码后插入；
- 写入失败也不应阻塞启动（仅记 ERROR 日志）。
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_sessionmaker
from app.models.user import User

logger = get_logger(__name__)


async def seed_admin_if_empty() -> None:
    settings = get_settings()
    if not settings.seed_admin_phone or not settings.seed_admin_password:
        logger.info("admin seed skipped (SEED_ADMIN_* env not set)")
        return
    sm = get_sessionmaker()
    try:
        async with sm() as session:
            count = (
                await session.execute(
                    select(func.count()).select_from(User).where(User.role == "admin")
                )
            ).scalar_one()
            if count and count > 0:
                logger.info(f"admin seed: existing admin(s)={count}, skip")
                return
            user = User(
                phone=settings.seed_admin_phone,
                name="Seed Admin",
                role="admin",
                status="active",
            )
            user.set_password(settings.seed_admin_password)
            session.add(user)
            await session.commit()
            logger.warning(
                f"admin seed: created seed admin phone={settings.seed_admin_phone}; "
                "change the password immediately on first login."
            )
    except Exception as exc:  # noqa: BLE001 — 启动期容错
        logger.error(f"admin seed failed: {exc.__class__.__name__}: {exc}")
