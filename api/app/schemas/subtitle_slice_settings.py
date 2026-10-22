"""语音切片设置 admin schema。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class SubtitleSliceSettingsRead(BaseModel):
    max_slice_seconds: int
    min_slice_ms: int
    silence_noise_db: float
    silence_min_duration_s: float
    min_silence_for_cut_ms: int


class SubtitleSliceSettingsUpdate(BaseModel):
    max_slice_seconds: int = Field(ge=8, le=60)
    min_slice_ms: int = Field(ge=200, le=3000)
    silence_noise_db: float = Field(ge=-50, le=-20)
    silence_min_duration_s: float = Field(ge=0.1, le=1.0)
    min_silence_for_cut_ms: int = Field(ge=100, le=800)
