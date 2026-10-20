"""Author-owned collections of notebooks."""
from __future__ import annotations

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

BigInt = BigInteger().with_variant(Integer, "sqlite")


class Collection(Base, TimestampMixin):
    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(16), nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(512), nullable=True)


class CollectionNotebook(Base):
    __tablename__ = "collection_notebooks"

    collection_id: Mapped[int] = mapped_column(
        BigInt,
        ForeignKey("collections.id", ondelete="CASCADE"),
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
