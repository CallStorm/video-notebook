"""聚合搜索请求 / 响应 schema。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Platform = Literal["youtube", "bilibili", "douyin"]
ALL_PLATFORMS: tuple[Platform, ...] = ("youtube", "bilibili", "douyin")


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    platforms: list[Platform] | None = None
    limit_per_platform: int = Field(default=12, ge=1, le=30)

    @field_validator("query")
    @classmethod
    def _strip_query(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("query 不能为空")
        return cleaned


class SearchResultItem(BaseModel):
    id: str
    title: str
    url: str
    thumbnail: str | None = None
    platform: Platform
    result_type: Literal["video"] = "video"
    duration: int | None = None
    uploader: str | None = None
    uploader_url: str | None = None
    view_count: int | None = None
    description: str | None = None


class PlatformSearchError(BaseModel):
    platform: Platform
    message: str


class SearchResponse(BaseModel):
    items: list[SearchResultItem]
    errors: list[PlatformSearchError] = []
