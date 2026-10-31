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
from app.observability.pipeline_log import (
    bind_run,
    end_pipeline_run,
    pipeline_stage,
    start_pipeline_run,
)
from app.observability.purge import request_purge

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
        },
        "observability-purge": {
            "task": "observability.purge",
            "schedule": 3600.0,
        },
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
    run_id: str | None = None,
    record_success: bool = True,
    notebook_id: int | None = None,
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
        _run_isolated(
            _run_pipeline(
                video_id,
                stage=stage,
                force=force,
                run_id=run_id,
                record_success=record_success,
                notebook_id=notebook_id,
            )
        )
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
    run_id: str | None = None,
    record_success: bool = True,
    notebook_id: int | None = None,
) -> None:
    from app.media.enqueue import pop_run_meta
    from app.observability.pipeline_log import log_event

    # Prefer Celery kwargs; fall back to Redis meta; else start a new run.
    rid = run_id
    rec = record_success
    if not rid:
        rid, rec = pop_run_meta(video_id)
    else:
        # consume redis meta if present so it does not leak
        pop_run_meta(video_id)
    nb_id = notebook_id
    if nb_id is None:
        try:
            from app.media.enqueue import _lookup_notebook_id

            nb_id = _lookup_notebook_id(video_id)
        except Exception:
            nb_id = None

    if rid:
        bind_run(rid, record_success=rec)
    else:
        start_pipeline_run(
            video_id=video_id,
            stage=stage,
            force=force,
            celery_task_id=None,
            notebook_id=nb_id,
        )

    status = "ok"
    err: str | None = None
    try:
        if stage == "full":
            from app.sources.fetch import run_fetch_pipeline

            with pipeline_stage("fetch", summary="download / persist"):
                await run_fetch_pipeline(video_id)
            async with get_sessionmaker()() as db:
                video = await db.get(Video, video_id)
                if video is None or not video.storage_key:
                    log_event(
                        "fetch",
                        "failed",
                        summary="no storage_key after fetch",
                    )
                    status = "failed"
                    err = "no storage_key after fetch"
                    return
                if video.status != "ready":
                    log_event(
                        "fetch",
                        "failed",
                        summary=f"status={video.status}",
                        error_text=(video.error_message or "")[:2000] or None,
                    )
                    status = "failed"
                    err = video.error_message or f"status={video.status}"
                    return
                subtitle_ready = video.subtitle_status == "ready" and not force
            if subtitle_ready:
                from app.subtitles.pipeline import run_overview_if_needed

                log_event(
                    "subtitle",
                    "skipped",
                    summary="字幕已就绪，跳过 ASR（沿用已有字幕，页面仍有字幕）",
                )
                await run_overview_if_needed(video_id, notebook_id=nb_id)
                await _refresh_vector_indexes(video_id)
                return
            from app.subtitles.pipeline import run_subtitle_pipeline

            await run_subtitle_pipeline(video_id, notebook_id=nb_id)
            await _refresh_vector_indexes(video_id)
            return

        from app.subtitles.pipeline import run_subtitle_pipeline

        await run_subtitle_pipeline(video_id, notebook_id=nb_id)
        await _refresh_vector_indexes(video_id)
    except Exception as exc:
        status = "failed"
        err = str(exc)[:2000]
        raise
    finally:
        end_pipeline_run(status=status, error_summary=err)



async def _refresh_vector_indexes(video_id: int) -> None:
    """Media/overview succeeded — refresh notebook vector indexes (non-fatal)."""
    try:
        from app.vector.enqueue import refresh_indexes_for_video

        await refresh_indexes_for_video(video_id)
    except Exception:
        logger.exception("vector refresh hook failed video_id=%s", video_id)


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
        from app.vector.enqueue import index_notebook_logged

        start_pipeline_run(
            video_id=None, stage="vector", force=force, notebook_id=int(notebook_id)
        )
        status = "ok"
        err = None
        try:
            st = await index_notebook_logged(int(notebook_id), force=bool(force))
            if st == "failed":
                status = "failed"
                err = "index_notebook returned failed"
            elif st == "skipped":
                status = "ok"
        except Exception as exc:
            status = "failed"
            err = str(exc)[:2000]
            raise
        finally:
            end_pipeline_run(status=status, error_summary=err)

    _run_isolated(_run())


@celery_app.task(name="observability.purge")
def observability_purge() -> None:
    request_purge()
