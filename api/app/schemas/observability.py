"""可观测 admin schema。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ObservabilitySettingsRead(BaseModel):
    pipeline_logs_enabled: bool
    llm_traces_enabled: bool
    retention_days: int
    success_sample_rate: float
    llm_record_full: bool
    llm_truncate_chars: int
    max_pipeline_run_rows: int
    max_llm_trace_rows: int
    langfuse_enabled: bool
    """预留：外接 Langfuse，当前未接入 SDK。"""


class ObservabilitySettingsUpdate(BaseModel):
    pipeline_logs_enabled: bool = False
    llm_traces_enabled: bool = False
    retention_days: int = Field(default=7, ge=1, le=90)
    success_sample_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    llm_record_full: bool = False
    llm_truncate_chars: int = Field(default=4096, ge=256, le=200000)
    max_pipeline_run_rows: int = Field(default=50000, ge=1000, le=500000)
    max_llm_trace_rows: int = Field(default=20000, ge=1000, le=200000)
    langfuse_enabled: bool = False


class PipelineRunEventItem(BaseModel):
    seq: int
    stage: str
    status: str
    summary: str | None
    detail_json: str | None
    error_text: str | None
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None


class PipelineRunListItem(BaseModel):
    run_id: str
    video_id: int | None
    notebook_id: int | None
    video_title: str | None = None
    stage: str
    status: str
    force: bool
    error_summary: str | None
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    event_count: int = 0
    events: list[PipelineRunEventItem] = []


class PipelineRunDetail(PipelineRunListItem):
    celery_task_id: str | None = None


class PipelineRunListResponse(BaseModel):
    items: list[PipelineRunListItem]
    total: int


class LlmTraceListItem(BaseModel):
    trace_id: str
    kind: str
    status: str
    notebook_id: int | None
    notebook_title: str | None = None
    video_id: int | None
    thread_id: int | None
    message_id: int | None
    provider: str | None
    model_name: str | None
    latency_ms: int | None
    prompt_tokens: int | None
    completion_tokens: int | None
    error_text: str | None
    started_at: datetime | None
    finished_at: datetime | None


class LlmSpanItem(BaseModel):
    seq: int
    name: str
    role: str | None
    content_text: str | None
    content_chars: int
    truncated: bool
    created_at: datetime | None


class LlmTraceDetail(LlmTraceListItem):
    spans: list[LlmSpanItem] = []


class LlmTraceListResponse(BaseModel):
    items: list[LlmTraceListItem]
    total: int
