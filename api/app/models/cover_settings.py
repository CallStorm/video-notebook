"""封面生成设置：提示词与采样参数（全站一行）。"""
from __future__ import annotations

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class CoverSettingsConfig(Base, TimestampMixin):
    """id 固定为 1。prompt 为空则用内置默认。"""

    __tablename__ = "cover_settings_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # svg | image
    mode: Mapped[str] = mapped_column(String(16), default="image", nullable=False)
    prompt_system: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_user: Mapped[str | None] = mapped_column(Text, nullable=True)
    temperature: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    force_keyword_motif: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    fallback_on_error: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    image_prompt_system: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_prompt_user: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_size: Mapped[str] = mapped_column(
        String(32), default="512x768", nullable=False
    )

