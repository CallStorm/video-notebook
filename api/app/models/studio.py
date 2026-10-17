"""Skill / Agent / StudioCapability / StudioTask / StudioArtifact 表。"""
from __future__ import annotations

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

# SQLite 上 BigInteger 不支持 autoincrement；用 Integer 变体让它在两种 DB 都能自增。
BigInt = BigInteger().with_variant(Integer, "sqlite")


class Skill(Base, TimestampMixin):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    uploaded_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    deleted_at: Mapped[object | None] = mapped_column(DateTime, nullable=True)


class Agent(Base, TimestampMixin):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), default="claude_code", nullable=False)
    skill_id: Mapped[int | None] = mapped_column(
        ForeignKey("skills.id"), nullable=True, index=True
    )
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=600, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    deleted_at: Mapped[object | None] = mapped_column(DateTime, nullable=True)


class StudioCapability(Base, TimestampMixin):
    __tablename__ = "studio_capabilities"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(16), nullable=True)
    format_key: Mapped[str] = mapped_column(String(32), nullable=False)
    agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("agents.id"), nullable=True, index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    form_json: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    deleted_at: Mapped[object | None] = mapped_column(DateTime, nullable=True)


class StudioTask(Base, TimestampMixin):
    __tablename__ = "studio_tasks"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    notebook_id: Mapped[int] = mapped_column(
        ForeignKey("notebooks.id"), nullable=False, index=True
    )
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    capability_id: Mapped[int] = mapped_column(
        ForeignKey("studio_capabilities.id"), nullable=False, index=True
    )
    agent_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    format_key: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    params_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[object | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[object | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[object | None] = mapped_column(DateTime, nullable=True)


class StudioArtifact(Base):
    __tablename__ = "studio_artifacts"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("studio_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
