"""流水线阶段日志 API（调用方零阻塞）。"""
from __future__ import annotations

import random
import threading
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Iterator

from app.observability.settings_cache import get_flags
from app.observability.writer import enqueue

_current_run: ContextVar[str | None] = ContextVar("obs_pipeline_run", default=None)
_seq_local = threading.local()


def current_run_id() -> str | None:
    return _current_run.get()


def start_pipeline_run(
    *,
    video_id: int | None,
    stage: str = "full",
    force: bool = False,
    celery_task_id: str | None = None,
    notebook_id: int | None = None,
    run_id: str | None = None,
) -> tuple[str | None, bool]:
    flags = get_flags()
    if not flags.pipeline_logs_enabled:
        return None, True
    rid = run_id or str(uuid.uuid4())
    record_success = random.random() < flags.success_sample_rate
    now = datetime.utcnow()
    enqueue(
        {
            "op": "pipeline_run_upsert",
            "run_id": rid,
            "video_id": video_id,
            "notebook_id": notebook_id,
            "stage": stage,
            "status": "running",
            "force": force,
            "record_success": record_success,
            "celery_task_id": celery_task_id,
            "started_at": now.isoformat(),
        }
    )
    _current_run.set(rid)
    _seq_local.n = 0
    _seq_local.record_success = record_success
    return rid, record_success


def bind_run(run_id: str | None, *, record_success: bool = True) -> None:
    if run_id:
        _current_run.set(run_id)
        _seq_local.n = 0
        _seq_local.record_success = record_success


def end_pipeline_run(
    *,
    status: str = "ok",
    error_summary: str | None = None,
    run_id: str | None = None,
) -> None:
    rid = run_id or _current_run.get()
    if not rid:
        return
    flags = get_flags()
    if not flags.pipeline_logs_enabled:
        return
    record_success = getattr(_seq_local, "record_success", True)
    if status == "ok" and not record_success:
        # drop success run that wasn't sampled: mark dropped, skip heavy
        enqueue(
            {
                "op": "pipeline_run_upsert",
                "run_id": rid,
                "status": "dropped",
                "finished_at": datetime.utcnow().isoformat(),
            }
        )
        return
    enqueue(
        {
            "op": "pipeline_run_upsert",
            "run_id": rid,
            "status": status,
            "error_summary": (error_summary or "")[:2000] or None,
            "finished_at": datetime.utcnow().isoformat(),
        }
    )


def log_event(
    stage: str,
    status: str,
    *,
    summary: str | None = None,
    detail: Any = None,
    error_text: str | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    duration_ms: int | None = None,
    run_id: str | None = None,
) -> None:
    flags = get_flags()
    if not flags.pipeline_logs_enabled:
        return
    rid = run_id or _current_run.get()
    if not rid:
        return
    # 未采样的成功 run：跳过非失败事件，失败仍记录
    if status != "failed" and not getattr(_seq_local, "record_success", True):
        return
    n = int(getattr(_seq_local, "n", 0)) + 1
    _seq_local.n = n
    now = datetime.utcnow()
    enqueue(
        {
            "op": "pipeline_event",
            "run_id": rid,
            "seq": n,
            "stage": stage,
            "status": status,
            "summary": summary,
            "detail": detail if status == "failed" else _thin_detail(detail, status),
            "error_text": error_text,
            "started_at": (started_at or now).isoformat(),
            "finished_at": finished_at.isoformat() if finished_at else (
                now.isoformat() if status != "started" else None
            ),
            "duration_ms": duration_ms,
        }
    )


def _thin_detail(detail: Any, status: str) -> Any:
    if detail is None:
        return None
    if status == "failed":
        return detail
    # success: summary only — keep small dicts
    if isinstance(detail, dict):
        out = {}
        for k, v in list(detail.items())[:12]:
            if isinstance(v, (int, float, bool)) or v is None:
                out[k] = v
            elif isinstance(v, str):
                out[k] = v[:120]
            else:
                out[k] = str(v)[:80]
        return out
    return str(detail)[:200]


@contextmanager
def pipeline_stage(
    stage: str,
    *,
    summary: str | None = None,
    detail: Any = None,
) -> Iterator[dict[str, Any]]:
    """Context manager: logs started → ok/failed."""
    flags = get_flags()
    bag: dict[str, Any] = {"summary": summary, "detail": detail}
    if not flags.pipeline_logs_enabled or not _current_run.get():
        yield bag
        return
    t0 = time.perf_counter()
    started = datetime.utcnow()
    log_event(stage, "started", summary=summary, detail=detail, started_at=started)
    try:
        yield bag
    except Exception as exc:
        ms = int((time.perf_counter() - t0) * 1000)
        log_event(
            stage,
            "failed",
            summary=bag.get("summary") or summary,
            detail=bag.get("detail") or detail,
            error_text=str(exc)[:4000],
            started_at=started,
            finished_at=datetime.utcnow(),
            duration_ms=ms,
        )
        raise
    else:
        ms = int((time.perf_counter() - t0) * 1000)
        log_event(
            stage,
            "ok",
            summary=bag.get("summary") or summary,
            detail=bag.get("detail") or detail,
            started_at=started,
            finished_at=datetime.utcnow(),
            duration_ms=ms,
        )
