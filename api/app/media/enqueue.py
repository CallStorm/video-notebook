"""API-side enqueue helpers for the media Celery queue."""
from __future__ import annotations

import logging
import uuid
from typing import Literal

from app.core.config import get_settings
from app.fetch_settings.runtime import get_cached_settings, get_settings_fresh
from app.observability.pipeline_log import log_event, start_pipeline_run

logger = logging.getLogger(__name__)

Stage = Literal["full", "subtitle_only"]

_TASK_KEY = "vnb:media:pipeline:task:{video_id}"
_RUN_KEY = "vnb:media:pipeline:run:{video_id}"


def _redis():
    import redis

    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def _task_key(video_id: int) -> str:
    return _TASK_KEY.format(video_id=video_id)


def _run_key(video_id: int) -> str:
    return _RUN_KEY.format(video_id=video_id)


def store_run_meta(
    video_id: int, run_id: str, *, record_success: bool, ttl_seconds: int
) -> None:
    import json

    try:
        payload = json.dumps({"run_id": run_id, "record_success": bool(record_success)})
        _redis().set(_run_key(video_id), payload, ex=max(300, int(ttl_seconds)))
    except Exception:
        logger.debug("store run meta failed video_id=%s", video_id, exc_info=True)


def pop_run_meta(video_id: int) -> tuple[str | None, bool]:
    import json

    try:
        r = _redis()
        key = _run_key(video_id)
        val = r.get(key)
        if val:
            r.delete(key)
        if not val:
            return None, True
        if val.startswith("{"):
            data = json.loads(val)
            return data.get("run_id"), bool(data.get("record_success", True))
        return val, True
    except Exception:
        logger.debug("pop run meta failed video_id=%s", video_id, exc_info=True)
        return None, True


def current_task_id(video_id: int) -> str | None:
    try:
        return _redis().get(_task_key(video_id))
    except Exception:
        logger.debug("read task id failed video_id=%s", video_id, exc_info=True)
        return None


def _store_task_id(video_id: int, task_id: str, *, ttl_seconds: int) -> None:
    try:
        _redis().set(_task_key(video_id), task_id, ex=max(300, int(ttl_seconds)))
    except Exception:
        logger.debug("store task id failed video_id=%s", video_id, exc_info=True)


def _clear_task_id(video_id: int) -> None:
    try:
        _redis().delete(_task_key(video_id))
    except Exception:
        logger.debug("clear task id failed video_id=%s", video_id, exc_info=True)



def _lookup_notebook_id(video_id: int) -> int | None:
    """Best-effort: first notebook that owns this video."""
    try:
        from sqlalchemy import create_engine, select
        from sqlalchemy.orm import Session

        from app.models.notebook import NotebookSource

        engine = create_engine(get_settings().database_sync_url, pool_pre_ping=True)
        try:
            with Session(engine) as session:
                return session.execute(
                    select(NotebookSource.notebook_id)
                    .where(NotebookSource.video_id == int(video_id))
                    .order_by(NotebookSource.sort.asc())
                    .limit(1)
                ).scalar_one_or_none()
        finally:
            engine.dispose()
    except Exception:
        logger.debug("lookup notebook_id failed video_id=%s", video_id, exc_info=True)
        return None


def enqueue_pipeline(
    video_id: int,
    *,
    stage: Stage = "full",
    force: bool = False,
    notebook_id: int | None = None,
) -> None:
    """Enqueue media.pipeline. No-op in test env.

    Always uses a fresh Celery task_id. Reusing a previously revoked id
    (e.g. pipeline-3) makes Celery discard the new message immediately.

    run_id is passed as a Celery kwarg (and mirrored in Redis) so the worker
    binds the same pipeline_runs row even if Redis meta is missing.
    """
    if get_settings().app_env == "test":
        return
    from app.media.worker import celery_app, media_pipeline

    snap = get_settings_fresh()
    prev = current_task_id(video_id)
    if prev:
        try:
            celery_app.control.revoke(prev, terminate=True, signal="SIGTERM")
        except Exception:
            logger.debug("revoke previous task ignored id=%s", prev, exc_info=True)

    task_id = f"pipeline-{video_id}-{uuid.uuid4().hex[:10]}"
    if notebook_id is None:
        notebook_id = _lookup_notebook_id(video_id)
    run_id, record_success = start_pipeline_run(
        video_id=video_id,
        stage=stage,
        force=force,
        celery_task_id=task_id,
        notebook_id=notebook_id,
    )
    if run_id:
        store_run_meta(
            video_id,
            run_id,
            record_success=record_success,
            ttl_seconds=snap.hard_time_limit + 600,
        )
        log_event(
            "enqueue",
            "ok",
            summary=f"queued stage={stage}",
            detail={"task_id": task_id, "stage": stage, "force": force},
            run_id=run_id,
        )

    media_pipeline.apply_async(
        args=[video_id, stage, force],
        kwargs={
            "run_id": run_id,
            "record_success": record_success,
            "notebook_id": notebook_id,
        },
        task_id=task_id,
        soft_time_limit=snap.soft_time_limit,
        time_limit=snap.hard_time_limit,
    )
    _store_task_id(video_id, task_id, ttl_seconds=snap.hard_time_limit + 600)
    logger.info(
        "enqueued media.pipeline video_id=%s stage=%s task_id=%s run_id=%s timeout=%ss",
        video_id,
        stage,
        task_id,
        run_id,
        snap.hard_time_limit,
    )


def cancel_pipeline(video_id: int) -> None:
    if get_settings().app_env == "test":
        return
    from app.media import slots
    from app.media.worker import celery_app

    task_id = current_task_id(video_id)
    if task_id:
        try:
            celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")
        except Exception:
            logger.warning("revoke failed task_id=%s", task_id, exc_info=True)
    _clear_task_id(video_id)
    slots.release(video_id)


def default_timeout_minutes() -> int:
    return get_cached_settings().task_timeout_minutes
