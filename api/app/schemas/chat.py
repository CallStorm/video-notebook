"""对话请求。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    source_ids: list[int] | None = None


class SourceSelection(BaseModel):
    selected_for_chat: bool
