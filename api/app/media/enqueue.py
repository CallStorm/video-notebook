"""API-side enqueue helpers for the media Celery queue."""
from __future__ import annotations

import logging
import uuid
from typing import Literal

from app.core.config import get_settings
from app.fetch_settings.runtime import get_cached_settings, get_settings_fresh

logger = logging.getLogger(__name__)

Stage = Literal["full", "subtitle_only"]

_TASK_KEY = "vnb:media:pipeline:task:{video_id}"


def _redis():
    import redis

    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def _task_key(video_id: int) -> str:
    return _TASK_KEY.format(video_id=video_id)


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


def enqueue_pipeline(
    video_id: int,
    *,
    stage: Stage = "full",
    force: bool = False,
) -> None:
    """Enqueue media.pipeline. No-op in test env.

    Always uses a fresh Celery task_id. Reusing a previously revoked id
    (e.g. pipeline-3) makes Celery discard the new message immediately.
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
    media_pipeline.apply_async(
        args=[video_id, stage, force],
        task_id=task_id,
        soft_time_limit=snap.soft_time_limit,
        time_limit=snap.hard_time_limit,
    )
    _store_task_id(video_id, task_id, ttl_seconds=snap.hard_time_limit + 600)
    logger.info(
        "enqueued media.pipeline video_id=%s stage=%s task_id=%s timeout=%ss",
        video_id,
        stage,
        task_id,
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
