"""抓取设置 admin schema。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class FetchSettingsRead(BaseModel):
    max_concurrent: int
    task_timeout_minutes: int
    chunk_parallel_enabled: bool
    chunk_count: int
    chunk_min_mb: int


class FetchSettingsUpdate(BaseModel):
    max_concurrent: int = Field(ge=1, le=8)
    task_timeout_minutes: int = Field(ge=5, le=180)
    chunk_parallel_enabled: bool
    chunk_count: int = Field(ge=2, le=8)
    chunk_min_mb: int = Field(ge=5, le=100)
