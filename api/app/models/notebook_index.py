"""笔记本向量索引状态（MySQL 只存状态；向量本体在 Qdrant）。"""
from __future__ import annotations

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

BigInt = BigInteger().with_variant(Integer, "sqlite")

INDEX_STATUSES = ("pending", "indexing", "ready", "failed", "skipped")


class NotebookIndexState(Base, TimestampMixin):
    __tablename__ = "notebook_index_states"

    notebook_id: Mapped[int] = mapped_column(
        BigInt,
        ForeignKey("notebooks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    vector_dim: Mapped[int | None] = mapped_column(Integer, nullable=True)
    indexed_at: Mapped[object | None] = mapped_column(DateTime, nullable=True)
    index_error: Mapped[str | None] = mapped_column(Text, nullable=True)
