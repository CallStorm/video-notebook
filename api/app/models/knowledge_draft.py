"""笔记本知识底稿 ORM：一本笔记本一份可编辑底稿。"""
from __future__ import annotations

from sqlalchemy import (
    JSON,
    BigInteger,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

BigInt = BigInteger().with_variant(Integer, "sqlite")


class NotebookKnowledgeDraft(Base, TimestampMixin):
    """每本笔记本至多一份知识底稿（统一 schema + 用户结论/勾选）。"""

    __tablename__ = "notebook_knowledge_drafts"
    __table_args__ = (
        UniqueConstraint("notebook_id", name="uq_notebook_knowledge_drafts_notebook_id"),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    notebook_id: Mapped[int] = mapped_column(
        ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_id: Mapped[int] = mapped_column(BigInt, nullable=False, index=True)
    strategy_id: Mapped[int | None] = mapped_column(
        ForeignKey("draft_strategies.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), default="ready", nullable=False)
    language: Mapped[str] = mapped_column(String(32), default="中文", nullable=False)
    model_ref: Mapped[str] = mapped_column(String(32), default="inherit", nullable=False)
    model_used: Mapped[str | None] = mapped_column(String(255), nullable=True)
    conclusion: Mapped[str] = mapped_column(Text, default="", nullable=False)
    content_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_video_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    source_note_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    focus: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_constraints: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
