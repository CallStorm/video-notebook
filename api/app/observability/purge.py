"""按保留天数与行数上限清理可观测数据。"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.observability import LlmSpan, LlmTrace, PipelineRun, PipelineRunEvent
from app.observability.settings_cache import get_flags

logger = logging.getLogger(__name__)


def purge_sync(session: Session) -> dict[str, int]:
    flags = get_flags(force=True)
    cutoff = datetime.utcnow() - timedelta(days=flags.retention_days)
    deleted = {"pipeline_events": 0, "pipeline_runs": 0, "llm_spans": 0, "llm_traces": 0}

    # time-based
    old_runs = session.execute(
        select(PipelineRun.run_id).where(PipelineRun.started_at < cutoff)
    ).scalars().all()
    if old_runs:
        r1 = session.execute(
            delete(PipelineRunEvent).where(PipelineRunEvent.run_id.in_(old_runs))
        )
        deleted["pipeline_events"] += r1.rowcount or 0
        r2 = session.execute(delete(PipelineRun).where(PipelineRun.run_id.in_(old_runs)))
        deleted["pipeline_runs"] += r2.rowcount or 0

    old_traces = session.execute(
        select(LlmTrace.trace_id).where(LlmTrace.started_at < cutoff)
    ).scalars().all()
    if old_traces:
        r3 = session.execute(delete(LlmSpan).where(LlmSpan.trace_id.in_(old_traces)))
        deleted["llm_spans"] += r3.rowcount or 0
        r4 = session.execute(delete(LlmTrace).where(LlmTrace.trace_id.in_(old_traces)))
        deleted["llm_traces"] += r4.rowcount or 0

    # row caps: delete oldest
    deleted["pipeline_runs"] += _cap_runs(session, flags.max_pipeline_run_rows)
    deleted["llm_traces"] += _cap_traces(session, flags.max_llm_trace_rows)
    return deleted


def _cap_runs(session: Session, max_rows: int) -> int:
    count = session.execute(select(func.count()).select_from(PipelineRun)).scalar() or 0
    if count <= max_rows:
        return 0
    overflow = count - max_rows
    ids = session.execute(
        select(PipelineRun.run_id).order_by(PipelineRun.started_at.asc()).limit(overflow)
    ).scalars().all()
    if not ids:
        return 0
    session.execute(delete(PipelineRunEvent).where(PipelineRunEvent.run_id.in_(ids)))
    r = session.execute(delete(PipelineRun).where(PipelineRun.run_id.in_(ids)))
    return r.rowcount or 0


def _cap_traces(session: Session, max_rows: int) -> int:
    count = session.execute(select(func.count()).select_from(LlmTrace)).scalar() or 0
    if count <= max_rows:
        return 0
    overflow = count - max_rows
    ids = session.execute(
        select(LlmTrace.trace_id).order_by(LlmTrace.started_at.asc()).limit(overflow)
    ).scalars().all()
    if not ids:
        return 0
    session.execute(delete(LlmSpan).where(LlmSpan.trace_id.in_(ids)))
    r = session.execute(delete(LlmTrace).where(LlmTrace.trace_id.in_(ids)))
    return r.rowcount or 0


def request_purge() -> None:
    from app.observability.writer import enqueue

    enqueue({"op": "purge"})
