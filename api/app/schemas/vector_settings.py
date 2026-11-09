"""向量配置 admin schema。"""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


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
    index_conclusions: bool
    index_draft: bool
    chunk_card_chars: int
    chunk_subtitles_chars: int
    chunk_notes_chars: int
    chunk_conclusions_chars: int
    chunk_draft_chars: int
    chunk_overlap_chars: int


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
    index_subtitles: bool = True
    index_notes: bool = True
    index_conclusions: bool = True
    index_draft: bool = True
    chunk_card_chars: int = Field(default=6000, ge=500, le=10000)
    chunk_subtitles_chars: int = Field(default=6000, ge=500, le=10000)
    chunk_notes_chars: int = Field(default=6000, ge=500, le=10000)
    chunk_conclusions_chars: int = Field(default=6000, ge=500, le=10000)
    chunk_draft_chars: int = Field(default=6000, ge=500, le=10000)
    chunk_overlap_chars: int = Field(default=200, ge=0, le=2000)

    @model_validator(mode="after")
    def overlap_fits_every_chunk(self):
        smallest = min(
            self.chunk_card_chars,
            self.chunk_subtitles_chars,
            self.chunk_notes_chars,
            self.chunk_conclusions_chars,
            self.chunk_draft_chars,
        )
        if self.chunk_overlap_chars >= smallest:
            raise ValueError("重叠字数必须小于每一类的切割字数")
        return self


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
