"""Celery app for the studio queue, plus leftover-task sweep."""
from __future__ import annotations

import asyncio
import shutil
import threading
import time
from collections.abc import Coroutine
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from celery import Celery
from celery.signals import worker_ready
from sqlalchemy import select, update

from app.core.config import get_settings
from app.db.session import dispose_engine, get_sessionmaker
from app.models.studio import StudioTask
from app.studio.plugins.registry import get_plugin
from app.studio.runner import execute_studio_task

_SWEEP_GRACE_SECONDS = 60
_SWEEP_INTERVAL_SECONDS = 600
_WORK_DIR_TTL_SECONDS = 24 * 3600


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _naive(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


settings = get_settings()
celery_app = Celery(
    "studio",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_default_queue="studio",
    # macOS billiard defaults to spawn. The spawned child never fills
    # Celery's fast-trace locals, so prefork crashes before the task runs
    # and the broker message is already acked.
    worker_pool="threads",
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "sweep-studio-tasks": {
            "task": "studio.sweep",
            "schedule": 600.0,
        }
    },
)


def _run_isolated(coro: Coroutine[Any, Any, None]) -> None:
    async def _inner() -> None:
        try:
            await coro
        finally:
            await dispose_engine()

    asyncio.run(_inner())


@celery_app.task(name="studio.run")
def studio_run(task_id: int) -> None:
    _run_isolated(execute_studio_task(task_id))


@celery_app.task(name="studio.sweep")
def studio_sweep() -> None:
    _run_isolated(sweep_studio_tasks(_now()))


def _sweep_loop() -> None:
    while True:
        time.sleep(_SWEEP_INTERVAL_SECONDS)
        _run_isolated(sweep_studio_tasks(_now()))


@worker_ready.connect
def _sweep_on_worker_ready(**_kwargs) -> None:
    _run_isolated(sweep_studio_tasks(_now()))
    threading.Thread(target=_sweep_loop, name="studio-sweep", daemon=True).start()


async def sweep_studio_tasks(now: datetime) -> None:
    now = _naive(now)
    cutoff = now.replace(tzinfo=UTC).timestamp() - _WORK_DIR_TTL_SECONDS
    factory = get_sessionmaker()
    async with factory() as session:
        rows = (
            await session.execute(
                select(StudioTask.id, StudioTask.started_at, StudioTask.format_key)
                .where(
                    StudioTask.status == "running",
                    StudioTask.started_at.is_not(None),
                )
            )
        ).all()
        for task_id, started_at, format_key in rows:
            if started_at is None:
                continue
            try:
                timeout_seconds = get_plugin(str(format_key)).timeout_seconds
            except KeyError:
                timeout_seconds = 600
            started = _naive(started_at)
            if started < now - timedelta(seconds=timeout_seconds + _SWEEP_GRACE_SECONDS):
                await session.execute(
                    update(StudioTask)
                    .where(
                        StudioTask.id == task_id,
                        StudioTask.status == "running",
                        StudioTask.deleted_at.is_(None),
                    )
                    .values(
                        status="failed",
                        error_code="process_failed",
                        finished_at=now,
                    )
                )

        stored = (
            await session.execute(
                select(StudioTask).where(StudioTask.result_json.is_not(None))
            )
        ).scalars().all()
        for task in stored:
            work_dir = (task.result_json or {}).get("work_dir")
            if not work_dir:
                continue
            path = Path(work_dir)
            try:
                if path.is_dir() and path.stat().st_mtime < cutoff:
                    shutil.rmtree(path, ignore_errors=True)
            except OSError:
                continue
        await session.commit()
