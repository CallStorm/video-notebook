"""语音切片设置：ASR 前 ffmpeg 静音切段参数（全站一行）。"""
from __future__ import annotations

from sqlalchemy import Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class SubtitleSliceSettingsConfig(Base, TimestampMixin):
    """id 固定为 1。"""

    __tablename__ = "subtitle_slice_settings_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    max_slice_seconds: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    min_slice_ms: Mapped[int] = mapped_column(Integer, default=600, nullable=False)
    silence_noise_db: Mapped[float] = mapped_column(Float, default=-32.0, nullable=False)
    silence_min_duration_s: Mapped[float] = mapped_column(Float, default=0.3, nullable=False)
    min_silence_for_cut_ms: Mapped[int] = mapped_column(Integer, default=200, nullable=False)
