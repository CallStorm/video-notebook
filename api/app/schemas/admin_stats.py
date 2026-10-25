"""Admin 运营总览大屏统计 schema。"""
from __future__ import annotations

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


class ReadinessStats(BaseModel):
    subtitle: ReadinessRate
    overview: ReadinessRate
    vector: ReadinessRate
    complete_notebooks: ReadinessRate


class FailureTopItem(BaseModel):
    stage: str
    count: int
    label: str | None = None


class FailureStats(BaseModel):
    top: list[FailureTopItem]
    window_hours: int = 24
    note: str | None = None


class AdminStatsResponse(BaseModel):
    observability: ObservabilityFlags
    content: ContentStats
    model_calls: ModelCallsStats
    tokens: TokenStats
    queues: QueueStats
    readiness: ReadinessStats
    failures: FailureStats
