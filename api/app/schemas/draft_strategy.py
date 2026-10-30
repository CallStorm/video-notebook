"""底稿策略 admin schema。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Kind = Literal["deep_read", "action", "glossary", "compare", "custom"]
SuggestedModel = Literal["inherit", "claude_code", "chat"]
GlobalModelRef = Literal["claude_code", "chat"]


class DraftStrategySettingsRead(BaseModel):
    default_prefix: str
    default_model_ref: GlobalModelRef
    max_tokens: int
    output_schema: dict[str, Any]
    kind_labels: dict[str, str]


class DraftStrategySettingsUpdate(BaseModel):
    default_prefix: str = Field(default="", max_length=20000)
    default_model_ref: GlobalModelRef = "claude_code"
    max_tokens: int = Field(default=200000, ge=1)


class DraftStrategyRead(BaseModel):
    id: int
    name: str
    title: str
    description: str
    kind: Kind
    prompt: str
    apply_default: bool
    enabled: bool
    suggested_model: SuggestedModel
    min_sources: int
    is_builtin: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DraftStrategyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    kind: Kind = "custom"
    prompt: str = Field(default="", max_length=50000)
    apply_default: bool = False
    enabled: bool = True
    suggested_model: SuggestedModel = "inherit"
    min_sources: int = Field(default=1, ge=1, le=20)


class DraftStrategyUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    prompt: str | None = Field(default=None, max_length=50000)
    apply_default: bool | None = None
    enabled: bool | None = None
    suggested_model: SuggestedModel | None = None
    min_sources: int | None = Field(default=None, ge=1, le=20)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    kind: Kind | None = None


class DraftStrategyPlaygroundRequest(BaseModel):
    strategy_id: int
    source_text: str | None = Field(default=None, max_length=100_000)
    video_id: int | None = None
    model_override: Literal["inherit", "claude_code", "chat"] | None = None


class DraftStrategyPlaygroundResponse(BaseModel):
    strategy_id: int
    model_used: str
    model_note: str | None = None
    raw_text: str
    preview: dict[str, Any] | None = None
    parse_ok: bool
    parse_error: str | None = None
