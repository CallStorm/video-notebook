"""Celery app for URL fetch + subtitle pipeline."""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Coroutine
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from celery import Celery
from celery.exceptions import SoftTimeLimitExceeded
from celery.signals import worker_ready
from sqlalchemy import or_, select

from app.core.config import get_settings
from app.db.session import dispose_engine, get_sessionmaker
from app.fetch_settings.runtime import get_settings_fresh
from app.models.notebook import Video

logger = logging.getLogger(__name__)

_SWEEP_INTERVAL_SECONDS = 60
_SWEEP_GRACE_SECONDS = 120

# Ensure ffmpeg/ffprobe are on PATH before any task runs (WinGet installs often
# missing from non-interactive Celery PATH).
try:
    from app.media.ffmpeg_path import ensure_ffmpeg_on_path

    ensure_ffmpeg_on_path()
except Exception:
    logger.exception("ffmpeg path bootstrap failed")

settings = get_settings()
celery_app = Celery(
    "media",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_default_queue="media",
    worker_pool="threads",
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "sweep-media-tasks": {
            "task": "media.sweep",
            "schedule": float(_SWEEP_INTERVAL_SECONDS),
        }
    },
)


def _run_isolated(coro: Coroutine[Any, Any, None]) -> None:
    """Run coroutine in a fresh event loop; drop any prior AsyncEngine first.

    Celery's thread pool reuses threads. A previous asyncio.run (e.g. settings
    reload) may leave an engine bound to a dead loop. Engine is thread-local.
    """
    from app.db.session import clear_engine_sync

    clear_engine_sync()

    async def _inner() -> None:
        try:
            await coro
        finally:
            await dispose_engine()

    asyncio.run(_inner())


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@celery_app.task(
    name="media.pipeline",
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def media_pipeline(
    self,
    video_id: int,
    stage: Literal["full", "subtitle_only"] = "full",
    force: bool = False,
) -> None:
    snap = get_settings_fresh()
    from app.media import slots

    acquired = slots.try_acquire(
        video_id,
        max_concurrent=snap.max_concurrent,
        lease_seconds=snap.hard_time_limit + 120,
    )
    if not acquired:
        logger.info("media slot full, retry video_id=%s", video_id)
        raise self.retry(countdown=5, max_retries=None)

    try:
        _run_isolated(_run_pipeline(video_id, stage=stage, force=force))
    except SoftTimeLimitExceeded:
        _run_isolated(_mark_timeout(video_id, stage=stage))
        raise
    finally:
        slots.release(video_id)


async def _run_pipeline(
    video_id: int,
    *,
    stage: Literal["full", "subtitle_only"],
    force: bool,
) -> None:
    if stage == "full":
        from app.sources.fetch import run_fetch_pipeline

        await run_fetch_pipeline(video_id)
        # Subtitle after successful fetch (run_fetch_pipeline used to kick in-process)
        async with get_sessionmaker()() as db:
            video = await db.get(Video, video_id)
            if video is None or not video.storage_key:
                return
            if video.status != "ready":
                return
            if video.subtitle_status == "ready" and not force:
                return
        from app.subtitles.pipeline import run_subtitle_pipeline

        await run_subtitle_pipeline(video_id)
        return

    from app.subtitles.pipeline import run_subtitle_pipeline

    await run_subtitle_pipeline(video_id)


async def _mark_timeout(
    video_id: int, *, stage: Literal["full", "subtitle_only"]
) -> None:
    msg = "任务超时，请重试或在后台「抓取设置」调高超时时间"
    async with get_sessionmaker()() as db:
        video = await db.get(Video, video_id)
        if video is None:
            return
        if stage == "full" and video.status in ("pending", "probing"):
            video.status = "failed"
            video.error_message = msg
        if video.subtitle_status == "processing":
            video.subtitle_status = "failed"
            video.subtitle_error = msg
        if video.overview_status == "processing":
            video.overview_status = "failed"
            video.overview_error = msg
        db.add(video)
        await db.commit()


@celery_app.task(name="media.sweep")
def media_sweep() -> None:
    _run_isolated(sweep_stale_media(_now()))


async def sweep_stale_media(now: datetime) -> int:
    snap = get_settings_fresh()
    cutoff = now - timedelta(seconds=snap.hard_time_limit + _SWEEP_GRACE_SECONDS)
    msg = "任务超时或 worker 中断，请重新抓取"
    marked = 0
    async with get_sessionmaker()() as db:
        result = await db.execute(
            select(Video).where(
                or_(
                    Video.status.in_(("pending", "probing")),
                    Video.subtitle_status == "processing",
                    Video.overview_status == "processing",
                )
            )
        )
        videos = list(result.scalars().all())
        for video in videos:
            updated = video.updated_at
            if updated is None:
                continue
            if getattr(updated, "tzinfo", None) is not None:
                updated = updated.astimezone(UTC).replace(tzinfo=None)
            if updated > cutoff:
                continue
            if video.status in ("pending", "probing"):
                video.status = "failed"
                video.error_message = msg
            if video.subtitle_status == "processing":
                video.subtitle_status = "failed"
                video.subtitle_error = msg
            if video.overview_status == "processing":
                video.overview_status = "failed"
                video.overview_error = msg
            db.add(video)
            marked += 1
        if marked:
            await db.commit()
            logger.info("media sweep marked failed count=%s", marked)
    return marked


def _sweep_loop() -> None:
    while True:
        time.sleep(_SWEEP_INTERVAL_SECONDS)
        try:
            media_sweep.delay()
        except Exception:
            logger.exception("media sweep enqueue failed")


@worker_ready.connect
def _on_worker_ready(**_kwargs) -> None:
    try:
        media_sweep.delay()
    except Exception:
        logger.exception("initial media sweep failed")
    thread = threading.Thread(target=_sweep_loop, name="media-sweep", daemon=True)
    thread.start()


@celery_app.task(name="vector.index_notebook")
def vector_index_notebook(notebook_id: int, force: bool = False) -> None:
    """Embed notebook document and upsert into Qdrant."""

    async def _run() -> None:
        from app.vector.indexer import index_notebook

        factory = get_sessionmaker()
        async with factory() as session:
            await index_notebook(session, int(notebook_id), force=bool(force))

    _run_isolated(_run())
