"""Agent Token 与异步门面任务。

明文 Token 只在创建响应里出现一次；库里只存 sha256。
"""
from __future__ import annotations

from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

BigInt = BigInteger().with_variant(Integer, "sqlite")


class AgentToken(Base, TimestampMixin):
    __tablename__ = "agent_tokens"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    token_hint: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    scopes: Mapped[list] = mapped_column(JSON, nullable=False)
    expires_at: Mapped[object | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[object | None] = mapped_column(DateTime, nullable=True)
    last_used_at: Mapped[object | None] = mapped_column(DateTime, nullable=True)


class AgentJob(Base, TimestampMixin):
    """封面 / 底稿等门面异步任务。结果只存 JSON，不存媒体字节。"""

    __tablename__ = "agent_jobs"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    notebook_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[object | None] = mapped_column(DateTime, nullable=True)
