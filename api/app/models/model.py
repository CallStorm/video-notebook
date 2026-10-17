"""Model 表：一个 name + provider + type 的命名模型，绑一条 credential。

类似 open-notebook/open_notebook/ai/models.py。role（chat/stt/...）的默认走
DefaultModel 表选择，model 表只声明「存在的模型」。
"""
from __future__ import annotations

from sqlalchemy import Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

# Model type 与 provider_registry 的 modalities 字符串一致
MODEL_TYPES = ("language", "embedding", "speech_to_text", "text_to_speech")


class Model(Base, TimestampMixin):
    __tablename__ = "models"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    type: Mapped[str] = mapped_column(
        Enum(*MODEL_TYPES, name="model_type"),
        nullable=False,
    )
    credential_id: Mapped[int] = mapped_column(
        ForeignKey("credentials.id", ondelete="RESTRICT"),
        nullable=False,
    )
    is_default_provider: Mapped[bool] = mapped_column(default=True, nullable=False)
    """若 true，新建的 default_models 记录可优先选这个；UI 上可隐藏此细节。"""

    __table_args__ = (
        Index("uq_model_provider_name_type", "provider", "name", "type", unique=True),
    )
