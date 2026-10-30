"""对话设置：历史轮数与上下文预算等（全站一行）。"""
from __future__ import annotations

from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class ChatSettingsConfig(Base, TimestampMixin):
    """id 固定为 1。history_limit 为最近 N 轮（用户+助手成对）。"""

    __tablename__ = "chat_settings_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    history_limit: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    max_context_chars: Mapped[int] = mapped_column(Integer, default=60_000, nullable=False)
