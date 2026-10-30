"""底稿策略 ORM：全局设置一行 + 策略多行。"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

BigInt = BigInteger().with_variant(Integer, "sqlite")

KIND_VALUES = ("deep_read", "action", "glossary", "compare", "custom")
MODEL_REF_VALUES = ("inherit", "claude_code", "chat")
GLOBAL_MODEL_REF_VALUES = ("claude_code", "chat")


class DraftStrategySettings(Base, TimestampMixin):
    """全站一行：全局前缀 + 默认模型引用。id 固定为 1。"""

    __tablename__ = "draft_strategy_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    default_prefix: Mapped[str] = mapped_column(Text, default="", nullable=False)
    default_model_ref: Mapped[str] = mapped_column(
        String(32), default="claude_code", nullable=False
    )
    max_tokens: Mapped[int] = mapped_column(Integer, default=200000, nullable=False)


class DraftStrategy(Base, TimestampMixin):
    """可配置的底稿生成策略（提示词 + 类型 + 默认模型）。"""

    __tablename__ = "draft_strategies"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    apply_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    suggested_model: Mapped[str] = mapped_column(
        String(32), default="inherit", nullable=False
    )
    min_sources: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
