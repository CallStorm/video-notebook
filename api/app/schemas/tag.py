"""Tag request/response schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    color: str | None = Field(default=None, max_length=16)


class TagUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    color: str | None = Field(default=None, max_length=16)


class TagBrief(BaseModel):
    id: int
    name: str
    color: str | None = None


class TagRead(TagBrief):
    notebook_count: int = 0
    created_at: str | None = None
    updated_at: str | None = None


class NotebookTagsRead(BaseModel):
    tag_ids: list[int]
    tags: list[TagBrief] = []


class NotebookTagsPut(BaseModel):
    tag_ids: list[int]


class AutoOrganizeSuggestedTag(BaseModel):
    temp_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=64)
    color: str | None = Field(default=None, max_length=16)


class AutoOrganizeNotebookBrief(BaseModel):
    id: int
    title: str
    description: str | None = None


class AutoOrganizeAssignment(BaseModel):
    notebook_id: int
    tag_temp_ids: list[str] = []


class AutoOrganizePreviewResponse(BaseModel):
    tags: list[AutoOrganizeSuggestedTag]
    assignments: list[AutoOrganizeAssignment]
    notebooks: list[AutoOrganizeNotebookBrief]
    message: str | None = None


class AutoOrganizeApplyRequest(BaseModel):
    tags: list[AutoOrganizeSuggestedTag]
    assignments: list[AutoOrganizeAssignment]


class AutoOrganizeApplyResponse(BaseModel):
    tags: list[TagRead]
