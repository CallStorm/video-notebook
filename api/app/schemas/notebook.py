"""Notebook / Source 相关的 Pydantic schema。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


# ── Tag brief (embedded on notebook list/detail) ────────────────
class TagBrief(BaseModel):
    id: int
    name: str
    color: str | None = None


# ── Notebook ─────────────────────────────────────────────────────
class NotebookCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    icon: str | None = Field(default=None, max_length=16)  # emoji（兼容旧客户端）
    cover_url: str | None = Field(default=None, max_length=512)


class NotebookUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    icon: str | None = Field(default=None, max_length=16)
    cover_url: str | None = Field(default=None, max_length=512)
    is_pinned: bool | None = None


class NotebookRead(BaseModel):
    id: int
    title: str
    description: str | None
    icon: str | None
    cover_url: str | None = None
    is_pinned: bool
    share_all: bool
    owner_id: int | None = None
    owner_name: str | None = None
    is_owner: bool | None = None
    source_count: int = 0
    note_count: int = 0
    match_hint: str | None = None
    # 向量索引状态（主人可见；列表/详情一并返回）
    index_status: str | None = None
    indexed_at: str | None = None
    index_error: str | None = None
    tags: list[TagBrief] = []
    created_at: str | None
    updated_at: str | None


class NotebookDetail(NotebookRead):
    """GET /notebooks/{id} 详情：含来源列表（不含字幕行）。"""


class NotebookListResponse(BaseModel):
    items: list[NotebookRead]
    total: int
    page: int
    size: int


# ── Source（Video） ────────────────────────────────────────────
class VideoRead(BaseModel):
    id: int
    source_type: Literal["upload", "url"]
    source_url: str | None
    storage_key: str | None
    mime: str | None
    duration_ms: int | None
    width: int | None
    height: int | None
    size_bytes: int | None
    content_hash: str | None
    status: Literal["pending", "probing", "ready", "failed"]
    error_message: str | None
    subtitle_status: Literal["pending", "processing", "ready", "failed"] = "pending"
    subtitle_error: str | None = None
    overview_status: Literal["pending", "processing", "ready", "failed"] = "pending"
    overview_text: str | None = None
    overview_error: str | None = None
    title: str | None
    created_at: str | None
    updated_at: str | None


class SourceSummary(BaseModel):
    """在 notebook 详情中，每个来源的简表。"""

    notebook_id: int
    video_id: int
    sort: int
    selected_for_chat: bool
    video: VideoRead


class NoteAssistRequest(BaseModel):
    action: Literal["write", "translate", "explain"]
    selection: str = Field(min_length=1, max_length=8000)
    instruction: str | None = Field(default=None, max_length=2000)
    prior: str | None = Field(default=None, max_length=8000)
    source_ids: list[int] | None = None
    note_ids: list[int] | None = None


class NoteCreate(BaseModel):
    """空白笔记。标题可空，空则用「未命名笔记」。"""

    title: str | None = Field(default=None, max_length=255)


class NoteRename(BaseModel):
    """更新笔记：可改标题、正文，至少一项。"""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    content_text: str | None = None

    @model_validator(mode="after")
    def require_one_field(self):
        if self.title is None and self.content_text is None:
            raise ValueError("需要提供 title 或 content_text")
        return self


class NoteRead(BaseModel):
    id: int
    notebook_id: int
    message_id: int | None
    title: str
    content_text: str
    citations: list[dict] = []
    selected_for_chat: bool = True
    created_at: str | None


class NotebookSourceRead(NotebookDetail):
    sources: list[SourceSummary]
    notes: list[NoteRead] = []


# ── 字幕 ──────────────────────────────────────────────────────
class SubtitleLineRead(BaseModel):
    line_no: int
    start_ms: int
    end_ms: int
    text: str


class SubtitleRead(BaseModel):
    source: str
    language: str | None
    format: str
    line_count: int
    lines: list[SubtitleLineRead]


class SubtitleView(BaseModel):
    """一条来源当前的字幕。生成中如果还有上一版，lines 仍返回旧内容。"""

    video_id: int
    subtitle_status: Literal["pending", "processing", "ready", "failed"]
    subtitle_error: str | None
    source: str | None = None
    language: str | None = None
    line_count: int = 0
    lines: list[SubtitleLineRead] = []


# ── URL fetch ──────────────────────────────────────────────────
class FetchUrlRequest(BaseModel):
    url: str = Field(min_length=1, max_length=1024)


class VideoRename(BaseModel):
    title: str = Field(min_length=1, max_length=255)
