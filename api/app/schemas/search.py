"""聚合搜索请求 / 响应 schema。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Platform = Literal["youtube", "bilibili", "douyin"]
# 默认聚合不含抖音（Bing 回退不稳定，暂时下线；代码与类型保留，显式传 platforms 仍可调）
ALL_PLATFORMS: tuple[Platform, ...] = ("youtube", "bilibili")


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
