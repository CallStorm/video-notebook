"""Collection request/response schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.notebook import NotebookRead


class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    icon: str | None = Field(default=None, max_length=16)


class CollectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    icon: str | None = Field(default=None, max_length=16)


class CollectionRead(BaseModel):
    id: int
    name: str
    icon: str | None
    notebook_count: int
    created_at: str | None
    updated_at: str | None


class CollectionDetail(CollectionRead):
    notebooks: list[NotebookRead] = []


class CollectionNotebooksPut(BaseModel):
    notebook_ids: list[int]


class NotebookCollectionsRead(BaseModel):
    collection_ids: list[int]


class NotebookCollectionsPut(BaseModel):
    collection_ids: list[int]
