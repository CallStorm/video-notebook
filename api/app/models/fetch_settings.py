"""抓取设置：并发、超时、分块并行下载（全站一行）。"""
from __future__ import annotations

from sqlalchemy import Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class FetchSettingsConfig(Base, TimestampMixin):
    """id 固定为 1。"""

    __tablename__ = "fetch_settings_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    max_concurrent: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    task_timeout_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)

    chunk_parallel_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    chunk_min_mb: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
