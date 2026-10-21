"""概览设置：字幕完成后是否自动生成 + 自定义提示词（全站一行）。"""
from __future__ import annotations

from sqlalchemy import Boolean, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class OverviewSettingsConfig(Base, TimestampMixin):
    """id 固定为 1。prompt_text 为空则用内置默认。"""

    __tablename__ = "overview_settings_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    auto_generate_after_subtitle: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
