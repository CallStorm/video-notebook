"""Author-owned tags for notebooks (many-to-many)."""
from __future__ import annotations

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

BigInt = BigInteger().with_variant(Integer, "sqlite")


class Tag(Base, TimestampMixin):
    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_tags_owner_id_name"),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)


class NotebookTag(Base):
    __tablename__ = "notebook_tags"

    tag_id: Mapped[int] = mapped_column(
        BigInt,
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )
    notebook_id: Mapped[int] = mapped_column(
        BigInt,
        ForeignKey("notebooks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    added_at: Mapped[object] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
