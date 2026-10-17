"""User 模型 — Phase 2 起第一个落地。

注意：迁移到 MySQL 时 Enum 类型会创建成字符串（`Enum('user','admin', name='user_role')`），
本仓库用 String 字段 + Pydantic enum 校验组合，避免 alembic 跨方言的可移植问题。
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

import bcrypt
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

UserRole = Literal["user", "admin"]
UserStatus = Literal["active", "disabled"]


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="user")
    status: Mapped[str] = mapped_column(String(16), default="active")
    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # ─── 密码（bcrypt 12 轮，绕过 passlib 避免其 bcrypt compat 问题） ──
    def set_password(self, raw: str) -> None:
        self.password_hash = bcrypt.hashpw(raw.encode(), bcrypt.gensalt(rounds=12)).decode()

    def check_password(self, raw: str) -> bool:
        try:
            return bcrypt.checkpw(raw.encode(), self.password_hash.encode())
        except ValueError:
            return False

    def __repr__(self) -> str:  # pragma: no cover - dev only
        return f"<User id={self.id} phone={self.phone!r} role={self.role}>"
