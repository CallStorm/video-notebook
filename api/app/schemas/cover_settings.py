"""封面生成设置 admin schema。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CoverSettingsRead(BaseModel):
    mode: Literal["image", "svg"]
    prompt_system: str
    prompt_user: str
    temperature: float
    force_keyword_motif: bool
    fallback_on_error: bool
    image_prompt_system: str
    image_prompt_user: str
    image_size: str
    is_custom_system: bool
    is_custom_user: bool
    is_custom_image_system: bool
    is_custom_image_user: bool
    default_prompt_system: str
    default_prompt_user: str
    default_temperature: float
    default_image_prompt_system: str
    default_image_prompt_user: str
    default_image_size: str
    default_mode: str


class CoverSettingsUpdate(BaseModel):
    mode: Literal["image", "svg"] = "image"
    prompt_system: str = Field(default="", max_length=8000)
    prompt_user: str = Field(default="", max_length=4000)
    temperature: float = Field(default=0.5, ge=0.0, le=2.0)
    force_keyword_motif: bool = True
    fallback_on_error: bool = False
    image_prompt_system: str = Field(default="", max_length=8000)
    image_prompt_user: str = Field(default="", max_length=4000)
    image_size: str = Field(default="512x768", max_length=32)

