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


class SystemPromptDraft(BaseModel):
    skill_name: str
    skill_description: str | None = None
    system_prompt: str


class AgentWrite(BaseModel):
    name: str
    skill_id: int | None
    system_prompt: str
    timeout_seconds: int = 600


class AgentRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    name: str
    provider: str
    skill_id: int | None
    system_prompt: str
    timeout_seconds: int
    is_active: bool
    updated_by: int
    created_at: datetime | None
    updated_at: datetime | None


class ClaudeCodeRead(BaseModel):
    api_key_set: bool
    base_url: str | None
    model_name: str


class ClaudeCodeUpdate(BaseModel):
    api_key: str | None = None
    base_url: str | None = None
    model_name: str


class FormatRead(BaseModel):
    key: str
    label: str


class CapabilityWrite(BaseModel):
    name: str
    icon: str | None = None
    format_key: str
    agent_id: int | None = None
    form: list[dict] = Field(default_factory=list)


class CapabilityUpdate(BaseModel):
    name: str | None = None
    icon: str | None = None
    agent_id: int | None = None
    form: list[dict] | None = None
    format_key: str | None = None


class CapabilityRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    name: str
    icon: str | None
    format_key: str
    agent_id: int | None
    enabled: bool
    is_builtin: bool
    form_json: list
    created_at: datetime | None
    updated_at: datetime | None


class TaskCreate(BaseModel):
    capability_id: int
    language: str | None = None
    video_ids: list[int] = Field(default_factory=list)
    note_ids: list[int] = Field(default_factory=list)
    fields: dict[str, str] = Field(default_factory=dict)


class TaskRename(BaseModel):
    title: str


class TaskRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    notebook_id: int
    owner_id: int
    capability_id: int
    agent_id: int | None = None
    format_key: str
    title: str
    status: str
    params_json: dict
    error_code: str | None
    error_message: str | None
    result_json: dict | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None


class ArtifactRead(BaseModel):
    id: int
    role: str
    filename: str
    mime: str


class TaskDetail(TaskRead):
    text_content: str | None = None
    artifacts: list[ArtifactRead] = Field(default_factory=list)
    pdf_error: str | None = None
