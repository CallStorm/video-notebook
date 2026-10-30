"""Collection request/response schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.notebook import NotebookRead


class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    icon: str | None = Field(default=None, max_length=16)
    cover_url: str | None = Field(default=None, max_length=512)


class CollectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    icon: str | None = Field(default=None, max_length=16)
    cover_url: str | None = Field(default=None, max_length=512)


class CollectionNotebookPreview(BaseModel):
    id: int
    title: str
    cover_url: str | None = None


class CollectionRead(BaseModel):
    id: int
    name: str
    icon: str | None
    cover_url: str | None = None
    notebook_count: int
    preview_notebooks: list[CollectionNotebookPreview] = []
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


class AutoOrganizeNotebookBrief(BaseModel):
    id: int
    title: str
    description: str | None = None


class AutoOrganizeSuggestedCollection(BaseModel):
    temp_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    notebook_ids: list[int] = []


class AutoOrganizePreviewResponse(BaseModel):
    collections: list[AutoOrganizeSuggestedCollection]
    notebooks: list[AutoOrganizeNotebookBrief]
    message: str | None = None


class AutoOrganizeApplyRequest(BaseModel):
    collections: list[AutoOrganizeSuggestedCollection]


class AutoOrganizeApplyResponse(BaseModel):
    collections: list[CollectionRead]

