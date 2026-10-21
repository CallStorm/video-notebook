"""DefaultModel 表：每个 role 选哪个 model。

role 集合：chat / tts / stt / logo / embedding。
logo：按名称生成 emoji 图标（绑定 language 模型）。
embedding：语义检索向量模型。
"""
from __future__ import annotations

from sqlalchemy import Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

DEFAULT_MODEL_ROLES = ("chat", "tts", "stt", "logo", "embedding")


class DefaultModel(Base, TimestampMixin):
    __tablename__ = "default_models"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    role: Mapped[str] = mapped_column(
        Enum(*DEFAULT_MODEL_ROLES, name="default_model_role"),
        nullable=False,
        unique=True,
    )
    model_id: Mapped[int] = mapped_column(
        ForeignKey("models.id", ondelete="RESTRICT"),
        nullable=False,
    )
