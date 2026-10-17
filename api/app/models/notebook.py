"""Notebook / Video / Subtitle / SubtitleLine / NotebookSource 表。

Phase 4 用。多租户 owner_id 隔离。
"""
from __future__ import annotations

from sqlalchemy import (
    CHAR,
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

# SQLite 上 BigInteger 不支持 autoincrement；用 Integer 变体让它在两种 DB 都能自增。
BigInt = BigInteger().with_variant(Integer, "sqlite")


# ── Notebook ─────────────────────────────────────────────────────
class Notebook(Base, TimestampMixin):
    __tablename__ = "notebooks"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(16), nullable=True)  # emoji
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # 字段保留。Discover / 公开浏览实装留 v2。
    share_all: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[object | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_notebooks_owner_pinned", "owner_id", "is_pinned"),
        Index("ix_notebooks_share_all", "share_all"),
    )


# ── Video ───────────────────────────────────────────────────────
class Video(Base, TimestampMixin):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(
        Enum("upload", "url", name="video_source_type"), nullable=False
    )
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mime: Mapped[str | None] = mapped_column(String(64), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(CHAR(40), nullable=True)
    # pending = 还没 ffprobe；probing = ffprobe 跑中；ready / failed = 终态
    status: Mapped[str] = mapped_column(
        Enum("pending", "probing", "ready", "failed", name="video_status"),
        nullable=False,
        default="pending",
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 字幕流水线：pending 等待 / processing 生成中 / ready 已有字幕 / failed 失败
    subtitle_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    subtitle_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 概览：重新生成时和字幕一起跑。pending 表示还没要求生成。
    overview_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    overview_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    overview_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 原始 filename
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        Index("uq_videos_owner_hash", "owner_id", "content_hash", unique=True),
    )


# ── Subtitle（v1 实际只写入 asr 路径；其它留 v2） ─────────────
class Subtitle(Base, TimestampMixin):
    __tablename__ = "subtitles"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    video_id: Mapped[int] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(
        Enum("embedded", "platform", "asr", name="subtitle_source"), nullable=False
    )
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    format: Mapped[str] = mapped_column(String(8), nullable=False, default="srt")
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    line_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __table_args__ = (
        # 同一视频同 source 同 language 同 version 唯一
        UniqueConstraint(
            "video_id", "source", "language", "version", name="uq_subtitle_video"
        ),
    )


class SubtitleLine(Base):
    __tablename__ = "subtitle_lines"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    subtitle_id: Mapped[int] = mapped_column(
        ForeignKey("subtitles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    start_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    end_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("ix_subtitle_lines_subtitle_line", "subtitle_id", "line_no", unique=True),
    )


# ── NotebookSource：notebook ↔ video 多对多 ─────────────────
class NotebookSource(Base):
    __tablename__ = "notebook_sources"

    notebook_id: Mapped[int] = mapped_column(
        ForeignKey("notebooks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    video_id: Mapped[int] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"),
        primary_key=True,
    )
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    selected_for_chat: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    __table_args__ = (Index("ix_notebook_sources_video", "video_id"),)


class ChatThread(Base, TimestampMixin):
    """一个笔记本一条对话。v1 不拆多个会话。"""

    __tablename__ = "chat_threads"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    notebook_id: Mapped[int] = mapped_column(
        ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    last_message_at: Mapped[object | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (UniqueConstraint("notebook_id", name="uq_chat_threads_notebook"),)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    thread_id: Mapped[int] = mapped_column(
        ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    citations_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    source_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class Note(Base, TimestampMixin):
    """从对话回答保存下来的笔记。一篇回答只保存一次。"""

    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    notebook_id: Mapped[int] = mapped_column(
        ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    citations_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    deleted_at: Mapped[object | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (UniqueConstraint("message_id", name="uq_notes_message"),)
