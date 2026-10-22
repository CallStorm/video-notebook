"""向量配置：索引字段开关 + Qdrant 连接（全站一行）。"""
from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class VectorSettingsConfig(Base, TimestampMixin):
    """id 固定为 1。"""

    __tablename__ = "vector_settings_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # pending | qdrant （一期默认 qdrant）
    vector_backend: Mapped[str] = mapped_column(String(32), default="qdrant", nullable=False)

    qdrant_url: Mapped[str] = mapped_column(
        String(512), default="http://127.0.0.1:6333", nullable=False
    )
    qdrant_api_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    qdrant_collection: Mapped[str] = mapped_column(
        String(128), default="notebooks", nullable=False
    )

    index_title: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    index_description: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    index_overview: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    index_subtitles: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    index_notes: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
