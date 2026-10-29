"""本内知识底稿 schema。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

ModelRef = Literal["inherit", "claude_code", "chat"]
Language = Literal["中文", "English"]
ExampleKind = Literal["life", "allusion", "work", "other"]


class DraftStrategyOption(BaseModel):
    id: int
    name: str
    title: str
    description: str
    kind: str
    apply_default: bool
    suggested_model: ModelRef
    min_sources: int


class KnowledgeDraftGenerateRequest(BaseModel):
    strategy_id: int
    language: Language = "中文"
    video_ids: list[int] = Field(default_factory=list)
    note_ids: list[int] = Field(default_factory=list)
    model: ModelRef = "inherit"
    focus: str | None = Field(default=None, max_length=2000)
    extra_constraints: str | None = Field(default=None, max_length=5000)


class KnowledgeDraftPoint(BaseModel):
    id: str
    text: str
    time: str | None = None
    evidence: str | None = None
    source_hint: str | None = None
    video_id: int | None = None
    checked: bool = False
    example: str | None = None
    example_kind: ExampleKind | None = None
    comment: str | None = None


class KnowledgeDraftTakeaway(BaseModel):
    id: str
    text: str
    checked: bool = False


class KnowledgeDraftConcept(BaseModel):
    term: str
    definition: str = ""


class KnowledgeDraftContent(BaseModel):
    theme: str = ""
    concepts: list[KnowledgeDraftConcept] = Field(default_factory=list)
    points: list[KnowledgeDraftPoint] = Field(default_factory=list)
    takeaways: list[KnowledgeDraftTakeaway] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class KnowledgeDraftRead(BaseModel):
    id: int
    notebook_id: int
    strategy_id: int | None
    strategy_title: str | None = None
    status: str
    language: str
    model_ref: str
    model_used: str | None = None
    # 兼容旧客户端：单字符串结论（多条用换行拼接）
    conclusion: str = ""
    # 方案 B：多条结论
    conclusions: list[str] = Field(default_factory=list)
    content: KnowledgeDraftContent
    source_video_ids: list[int]
    source_note_ids: list[int]
    focus: str | None = None
    extra_constraints: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class KnowledgeDraftUpdateRequest(BaseModel):
    # 新：多条结论；旧：单字符串。二者都传时以 conclusions 为准。
    conclusions: list[str] | None = None
    conclusion: str | None = Field(default=None, max_length=8000)
    checked_point_ids: list[str] | None = None
    checked_takeaway_ids: list[str] | None = None
    point_text_updates: dict[str, str] | None = None
    # value 为 null/空串表示删除评论
    point_comment_updates: dict[str, str | None] | None = None

    @field_validator("conclusions")
    @classmethod
    def _trim_conclusions(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        out: list[str] = []
        for item in v:
            s = str(item or "").strip()
            if s:
                out.append(s[:4000])
        if len(out) > 40:
            raise ValueError("conclusions 最多 40 条")
        return out


class KnowledgeDraftPointAskMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class KnowledgeDraftPointAskRequest(BaseModel):
    point_id: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=2000)
    history: list[KnowledgeDraftPointAskMessage] = Field(default_factory=list)


class KnowledgeDraftPointAskResponse(BaseModel):
    point_id: str
    answer: str

