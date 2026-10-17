"""Pydantic schemas for credentials / models / default-models / providers."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ─── Provider 元数据（前端下拉与文档用） ─────────────────────────────
class ProviderInfo(BaseModel):
    name: str
    display_name: str
    modalities: list[str]
    default_base_url: str | None = None
    test_model: str | None = None
    docs_url: str | None = None
    anthropic_compat: bool = False


# ─── Credential ──────────────────────────────────────────────────────────
class CredentialRead(BaseModel):
    id: int
    name: str
    provider: str
    modalities: list[str]
    base_url: str | None
    config: dict | None = None
    api_key_masked: str
    has_api_key: bool
    is_builtin: bool
    updated_at: str | None


class CredentialCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    provider: str = Field(min_length=1, max_length=32)
    api_key: str = Field(min_length=1)
    modalities: list[str] | None = None
    base_url: str | None = None
    config: dict | None = None


class CredentialUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    api_key: str | None = None
    modalities: list[str] | None = None
    base_url: str | None = None
    config: dict | None = None


# ─── Model ───────────────────────────────────────────────────────────────
class ModelRead(BaseModel):
    id: int
    name: str
    provider: str
    type: str
    credential_id: int
    is_default_provider: bool
    created_at: str | None


class ModelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    provider: str = Field(min_length=1, max_length=32)
    type: Literal["language", "embedding", "speech_to_text", "text_to_speech"]
    credential_id: int


class ModelTestRequest(BaseModel):
    """暂时没参数——后端用 model 元数据决定怎么测。"""

    prompt: str | None = Field(default=None, max_length=2000)


class ModelTestResult(BaseModel):
    ok: bool
    latency_ms: int
    provider: str
    message: str | None = None
    error: str | None = None
    response: str | None = None


class DiscoveredModel(BaseModel):
    """模型发现结果。provider 字段在响应里填，调用方也能从前端的 credential 上下文推断。"""

    name: str
    provider: str | None = None
    description: str | None = None


class DiscoverRequest(BaseModel):
    credential_id: int


class BulkRegisterRequest(BaseModel):
    credential_id: int
    models: list[BulkRegisterItem]


class BulkRegisterItem(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    type: Literal["language", "embedding", "speech_to_text", "text_to_speech"]


class BulkRegisterResponse(BaseModel):
    created: list[ModelRead]
    skipped: list[str]  # names that already existed


class DiscoverResponse(BaseModel):
    items: list[DiscoveredModel]


BulkRegisterRequest.model_rebuild()


# ─── DefaultModel ────────────────────────────────────────────────────────
class DefaultModelRead(BaseModel):
    role: str
    model_id: int | None


class DefaultModelSet(BaseModel):
    model_id: int
