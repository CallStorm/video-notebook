"""有界队列 + 后台线程批量落库。永不阻塞调用方。"""
from __future__ import annotations

import json
import logging
import queue
import threading
import time
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

_QUEUE_MAX = 2000
_BATCH = 40
_FLUSH_SECONDS = 0.4

_q: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=_QUEUE_MAX)
_started = False
_start_lock = threading.Lock()
_drop_count = 0


def enqueue(item: dict[str, Any]) -> None:
    """Put item; on overflow drop oldest then retry once. Never raises to caller."""
    global _drop_count
    _ensure_started()
    try:
        _q.put_nowait(item)
        return
    except queue.Full:
        pass
    try:
        _q.get_nowait()
        _drop_count += 1
    except queue.Empty:
        pass
    try:
        _q.put_nowait(item)
    except queue.Full:
        _drop_count += 1


def dropped_count() -> int:
    return _drop_count


def _ensure_started() -> None:
    global _started
    if _started:
        return
    with _start_lock:
        if _started:
            return
        t = threading.Thread(target=_loop, name="obs-writer", daemon=True)
        t.start()
        _started = True


def _loop() -> None:
    while True:
        batch: list[dict[str, Any]] = []
        try:
            item = _q.get(timeout=_FLUSH_SECONDS)
            batch.append(item)
        except queue.Empty:
            continue
        deadline = time.monotonic() + _FLUSH_SECONDS
        while len(batch) < _BATCH and time.monotonic() < deadline:
            try:
                batch.append(_q.get_nowait())
            except queue.Empty:
                break
        try:
            _flush(batch)
        except Exception:
            logger.exception("observability flush failed count=%s", len(batch))


def _flush(batch: list[dict[str, Any]]) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.core.config import get_settings
    from app.models.observability import (
        LlmSpan,
        LlmTrace,
        PipelineRun,
        PipelineRunEvent,
    )

    engine = create_engine(get_settings().database_sync_url, pool_pre_ping=True)
    try:
        with Session(engine) as session:
            for item in batch:
                kind = item.get("op")
                try:
                    if kind == "pipeline_run_upsert":
                        _upsert_run(session, PipelineRun, item)
                    elif kind == "pipeline_event":
                        session.add(
                            PipelineRunEvent(
                                run_id=item["run_id"],
                                seq=int(item.get("seq") or 0),
                                stage=item["stage"],
                                status=item["status"],
                                summary=_clip(item.get("summary"), 512),
                                detail_json=_json_or_none(item.get("detail")),
                                error_text=_clip(item.get("error_text"), 8000),
                                started_at=_dt(item["started_at"]),
                                finished_at=_dt(item.get("finished_at")),
                                duration_ms=item.get("duration_ms"),
                            )
                        )
                    elif kind == "llm_trace_upsert":
                        _upsert_trace(session, LlmTrace, item)
                    elif kind == "llm_span":
                        session.add(
                            LlmSpan(
                                trace_id=item["trace_id"],
                                seq=int(item.get("seq") or 0),
                                name=item["name"],
                                role=item.get("role"),
                                content_text=item.get("content_text"),
                                content_chars=int(item.get("content_chars") or 0),
                                truncated=bool(item.get("truncated")),
                                created_at=_dt(item.get("created_at") or item.get("started_at")),
                            )
                        )
                    elif kind == "purge":
                        from app.observability.purge import purge_sync

                        purge_sync(session)
                except Exception:
                    logger.exception("observability item failed op=%s", kind)
                    session.rollback()
            session.commit()
    finally:
        engine.dispose()


def _upsert_run(session, model, item: dict[str, Any]) -> None:
    from sqlalchemy import select

    row = session.execute(
        select(model).where(model.run_id == item["run_id"])
    ).scalar_one_or_none()
    if row is None:
        row = model(run_id=item["run_id"])
        session.add(row)
    for key in (
        "video_id",
        "notebook_id",
        "stage",
        "status",
        "force",
        "record_success",
        "celery_task_id",
        "error_summary",
        "duration_ms",
    ):
        if key in item and item[key] is not None:
            setattr(row, key, item[key])
    if "started_at" in item and item["started_at"]:
        row.started_at = _dt(item["started_at"])
    if "finished_at" in item:
        row.finished_at = _dt(item["finished_at"])


def _upsert_trace(session, model, item: dict[str, Any]) -> None:
    from sqlalchemy import select

    row = session.execute(
        select(model).where(model.trace_id == item["trace_id"])
    ).scalar_one_or_none()
    if row is None:
        row = model(trace_id=item["trace_id"])
        session.add(row)
    for key in (
        "kind",
        "status",
        "notebook_id",
        "video_id",
        "thread_id",
        "message_id",
        "provider",
        "model_name",
        "error_text",
        "prompt_tokens",
        "completion_tokens",
        "latency_ms",
    ):
        if key in item and item[key] is not None:
            setattr(row, key, item[key])
    if "started_at" in item and item["started_at"]:
        row.started_at = _dt(item["started_at"])
    if "finished_at" in item:
        row.finished_at = _dt(item["finished_at"])


def _dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, (int, float)):
        return datetime.utcfromtimestamp(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", ""))
        except ValueError:
            return datetime.utcnow()
    return datetime.utcnow()


def _clip(text: Any, n: int) -> str | None:
    if text is None:
        return None
    s = str(text)
    return s if len(s) <= n else s[:n]


def _json_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return _clip(value, 8000)
    try:
        return _clip(json.dumps(value, ensure_ascii=False, default=str), 8000)
    except Exception:
        return None


def drain(*, timeout_seconds: float = 5.0) -> int:
    """Block until queue is empty (best-effort). For scripts/shutdown."""
    deadline = time.monotonic() + max(0.5, float(timeout_seconds))
    while time.monotonic() < deadline:
        if _q.empty():
            time.sleep(0.45)
            if _q.empty():
                return 0
        time.sleep(0.05)
    return _q.qsize()
