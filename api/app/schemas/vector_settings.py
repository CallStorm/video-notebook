"""向量配置 admin schema。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class VectorSettingsRead(BaseModel):
    vector_backend: str
    qdrant_url: str
    qdrant_api_key: str | None = None
    qdrant_api_key_set: bool = False
    qdrant_collection: str
    index_title: bool
    index_description: bool
    index_overview: bool
    index_subtitles: bool
    index_notes: bool


class VectorSettingsUpdate(BaseModel):
    vector_backend: str = Field(default="qdrant", max_length=32)
    qdrant_url: str = Field(min_length=1, max_length=512)
    qdrant_api_key: str | None = Field(default=None, max_length=512)
    # True = 清空已存的 api_key
    clear_qdrant_api_key: bool = False
    qdrant_collection: str = Field(min_length=1, max_length=128)
    index_title: bool = True
    index_description: bool = True
    index_overview: bool = True
    index_subtitles: bool = False
    index_notes: bool = False


class VectorReindexAllResult(BaseModel):
    queued: int
    message: str


class NotebookIndexStateRead(BaseModel):
    notebook_id: int
    status: str
    content_hash: str | None = None
    model_name: str | None = None
    vector_dim: int | None = None
    indexed_at: str | None = None
    index_error: str | None = None


class NotebookReindexResult(BaseModel):
    notebook_id: int
    status: str
    message: str
