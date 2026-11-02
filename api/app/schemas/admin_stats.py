"""Admin 运营总览大屏统计 schema。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ObservabilityFlags(BaseModel):
    pipeline_logs_enabled: bool
    llm_traces_enabled: bool


class ContentStats(BaseModel):
    notebooks: int
    videos: int
    notes: int
    share_all_notebooks: int = Field(
        description="share_all=true 且未删除的笔记本数（全站共享）"
    )


class CallCount(BaseModel):
    """某类调用计数；unavailable 表示无埋点或无法统计。"""

    count: int | None = None
    unavailable: bool = False
    reason: str | None = None


class DailyCount(BaseModel):
    date: str  # YYYY-MM-DD（UTC 日历日）
    llm: int | None = None
    embed: int | None = None
    asr: int | None = None
    tts: int | None = None
    tokens: int | None = None


class ModelCallsStats(BaseModel):
    llm: CallCount
    embed: CallCount
    asr: CallCount
    tts: CallCount
    trend_7d: list[DailyCount]


class TokenStats(BaseModel):
    total: int | None = None
    unavailable: bool = False
    reason: str | None = None
    trend_7d: list[DailyCount]


class QueueStats(BaseModel):
    media_depth: int | None = None
    studio_depth: int | None = None
    index_backlog: int  # pending + indexing
    studio_queued: int
    redis_ok: bool = True
    redis_error: str | None = None


class ReadinessRate(BaseModel):
    ready: int
    total: int
    rate: float | None = None  # 0~1；total=0 时为 null


class StageBreakdown(BaseModel):
    """来源上还没就绪的三档。pending 是未开始。"""

    failed: int = 0
    processing: int = 0
    pending: int = 0


class VectorBreakdown(BaseModel):
    """向量环下面单独点名的四类。空壳不混进失败或入库中。"""

    failed: int = 0
    indexing: int = 0
    stale: int = 0
    empty: int = 0


class ReadinessExceptionItem(BaseModel):
    notebook_id: int
    title: str
    owner_name: str | None = None
    is_mine: bool = False
    subtitle_failed: int = 0
    subtitle_processing: int = 0
    subtitle_pending: int = 0
    subtitle_total: int = 0
    overview_failed: int = 0
    overview_processing: int = 0
    overview_pending: int = 0
    overview_total: int = 0
    index_status: str = "pending"
    index_stale: bool = False
    error: str | None = None


class ReadinessStats(BaseModel):
    subtitle: ReadinessRate
    overview: ReadinessRate
    vector: ReadinessRate
    complete_notebooks: ReadinessRate
    subtitle_detail: StageBreakdown = Field(default_factory=StageBreakdown)
    overview_detail: StageBreakdown = Field(default_factory=StageBreakdown)
    vector_detail: VectorBreakdown = Field(default_factory=VectorBreakdown)
    exceptions: list[ReadinessExceptionItem] = Field(default_factory=list)
    exception_total: int = 0


class FailureTopItem(BaseModel):
    stage: str
    count: int
    label: str | None = None


class FailureStats(BaseModel):
    top: list[FailureTopItem]
    window_hours: int = 24
    # window = 近 24 小时流水线事件；stock = 业务表现有失败
    basis: Literal["window", "stock"] = "window"
    note: str | None = None


class AdminStatsResponse(BaseModel):
    observability: ObservabilityFlags
    content: ContentStats
    model_calls: ModelCallsStats
    tokens: TokenStats
    queues: QueueStats
    readiness: ReadinessStats
    failures: FailureStats
