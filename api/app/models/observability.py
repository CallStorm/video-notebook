"""可观测：流水线运行日志 + 内建 LLM 追踪（默认全关）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class ObservabilitySettingsConfig(Base, TimestampMixin):
    """id 固定为 1。默认关闭，避免写库拖慢主链路。"""

    __tablename__ = "observability_settings_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pipeline_logs_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    llm_traces_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    retention_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    success_sample_rate: Mapped[float] = mapped_column(
        Float, default=1.0, nullable=False
    )
    """成功 run 采样率 0~1；失败始终记录。"""
    llm_record_full: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    llm_truncate_chars: Mapped[int] = mapped_column(
        Integer, default=4096, nullable=False
    )
    max_pipeline_run_rows: Mapped[int] = mapped_column(
        Integer, default=50000, nullable=False
    )
    max_llm_trace_rows: Mapped[int] = mapped_column(
        Integer, default=20000, nullable=False
    )
    # stub for future Langfuse; unused in v1
    langfuse_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    __table_args__ = (
        Index("ix_pipeline_runs_video_started", "video_id", "started_at"),
        Index("ix_pipeline_runs_status_started", "status", "started_at"),
        Index("ix_pipeline_runs_started", "started_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    video_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    notebook_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stage: Mapped[str] = mapped_column(String(32), default="full", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="running", nullable=False)
    # running | ok | failed | dropped
    force: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    record_success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    celery_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class PipelineRunEvent(Base):
    __tablename__ = "pipeline_run_events"
    __table_args__ = (
        Index("ix_pipeline_run_events_run_seq", "run_id", "seq"),
        Index("ix_pipeline_run_events_stage_started", "stage", "started_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    seq: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    # enqueue | fetch | subtitle | asr | overview | vector
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    # started | ok | failed | skipped
    summary: Mapped[str | None] = mapped_column(String(512), nullable=True)
    detail_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class LlmTrace(Base):
    __tablename__ = "llm_traces"
    __table_args__ = (
        Index("ix_llm_traces_kind_started", "kind", "started_at"),
        Index("ix_llm_traces_status_started", "status", "started_at"),
        Index("ix_llm_traces_started", "started_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    # chat | overview | studio
    status: Mapped[str] = mapped_column(String(16), default="running", nullable=False)
    notebook_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    video_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    thread_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class LlmSpan(Base):
    __tablename__ = "llm_spans"
    __table_args__ = (Index("ix_llm_spans_trace_seq", "trace_id", "seq"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    seq: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    # system | user | history | generation | notes
    role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_chars: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    truncated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
