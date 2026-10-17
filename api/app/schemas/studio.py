"""Studio / skill / agent / capability 请求与响应模型。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SkillRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    name: str
    description: str | None
    version: str | None
    storage_path: str
    file_count: int
    size_bytes: int
    uploaded_by: int
    created_at: datetime | None
    updated_at: datetime | None


class SkillUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    version: str | None = Field(default=None, max_length=64)
