"""概览生成设置 admin schema。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class OverviewSettingsRead(BaseModel):
    auto_generate_after_subtitle: bool
    prompt_text: str
    """当前生效提示词（空配置时回填内置默认，便于前端展示）。"""
    is_custom_prompt: bool
    """是否使用了自定义提示词（非空且与默认不同，或仅非空）。"""
    default_prompt: str
    """内置默认，供「恢复默认」。"""


class OverviewSettingsUpdate(BaseModel):
    auto_generate_after_subtitle: bool = True
    prompt_text: str = Field(default="", max_length=8000)
    """传空字符串表示改回内置默认（存 NULL）。"""
