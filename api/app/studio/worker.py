"""Celery app for the studio queue, plus leftover-task sweep."""
from __future__ import annotations

import asyncio
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from celery import Celery
from celery.signals import worker_ready
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import get_sessionmaker
from app.models.studio import Agent, StudioTask
from app.studio.runner import execute_studio_task

_SWEEP_GRACE_SECONDS = 60
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
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "sweep-studio-tasks": {
            "task": "studio.sweep",
            "schedule": 600.0,
        }
    },
)


@celery_app.task(name="studio.run")
def studio_run(task_id: int) -> None:
    asyncio.run(execute_studio_task(task_id))


@celery_app.task(name="studio.sweep")
def studio_sweep() -> None:
    asyncio.run(sweep_studio_tasks(_now()))


@worker_ready.connect
def _sweep_on_worker_ready(**_kwargs) -> None:
    asyncio.run(sweep_studio_tasks(_now()))


async def sweep_studio_tasks(now: datetime) -> None:
    now = _naive(now)
    cutoff = now.replace(tzinfo=UTC).timestamp() - _WORK_DIR_TTL_SECONDS
    factory = get_sessionmaker()
    async with factory() as session:
        rows = (
            await session.execute(
                select(StudioTask, Agent.timeout_seconds).join(
                    Agent, Agent.id == StudioTask.agent_id
                ).where(
                    StudioTask.status == "running",
                    StudioTask.started_at.is_not(None),
                )
            )
        ).all()
        for task, timeout_seconds in rows:
            started = _naive(task.started_at)
            if started < now - timedelta(seconds=timeout_seconds + _SWEEP_GRACE_SECONDS):
                task.status = "failed"
                task.error_code = "process_failed"
                task.finished_at = now
                session.add(task)

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
