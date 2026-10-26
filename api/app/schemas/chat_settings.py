"""对话设置 admin schema。"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.chat_settings.defaults import (
    MAX_CHAT_HISTORY_LIMIT,
    MAX_MAX_CONTEXT_CHARS,
    MIN_CHAT_HISTORY_LIMIT,
    MIN_MAX_CONTEXT_CHARS,
)


class ChatSettingsRead(BaseModel):
    history_limit: int
    """最近保留的对话轮数（用户+助手成对）。"""
    default_history_limit: int
    """内置 / 环境默认，供前端展示。"""
    max_context_chars: int
    """上下文字符预算（字幕+笔记+问题+历史）。"""
    default_max_context_chars: int
    """内置 / 环境默认。"""


class ChatSettingsUpdate(BaseModel):
    history_limit: int = Field(
        ge=MIN_CHAT_HISTORY_LIMIT, le=MAX_CHAT_HISTORY_LIMIT
    )
    max_context_chars: int = Field(
        ge=MIN_MAX_CONTEXT_CHARS, le=MAX_MAX_CONTEXT_CHARS
    )
