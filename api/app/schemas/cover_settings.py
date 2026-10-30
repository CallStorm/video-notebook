"""封面生成设置 admin schema（仅文生图）。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class CoverSettingsRead(BaseModel):
    image_prompt_system: str
    image_prompt_user: str
    image_size: str
    is_custom_image_system: bool
    is_custom_image_user: bool
    default_image_prompt_system: str
    default_image_prompt_user: str
    default_image_size: str


class CoverSettingsUpdate(BaseModel):
    image_prompt_system: str = Field(default="", max_length=8000)
    image_prompt_user: str = Field(default="", max_length=4000)
    image_size: str = Field(default="512x768", max_length=32)
