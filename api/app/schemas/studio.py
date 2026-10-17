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


class AgentWrite(BaseModel):
    name: str
    skill_id: int | None
    model_name: str
    system_prompt: str
    timeout_seconds: int = 600


class AgentRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    name: str
    provider: str
    skill_id: int | None
    model_name: str
    system_prompt: str
    timeout_seconds: int
    is_active: bool
    updated_by: int
    created_at: datetime | None
    updated_at: datetime | None
