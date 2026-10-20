"""Admin 抓取设置服务。"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.fetch_settings.runtime import set_runtime_snapshot
from app.models.fetch_settings import FetchSettingsConfig
from app.schemas.fetch_settings import FetchSettingsRead, FetchSettingsUpdate

_ROW_ID = 1


async def _ensure_row(session: AsyncSession) -> FetchSettingsConfig:
    row = await session.get(FetchSettingsConfig, _ROW_ID)
    if row is None:
        row = FetchSettingsConfig(
            id=_ROW_ID,
            max_concurrent=2,
            task_timeout_minutes=30,
            chunk_parallel_enabled=True,
            chunk_count=4,
            chunk_min_mb=20,
        )
        session.add(row)
        await session.flush()
    return row


def _publish(row: FetchSettingsConfig) -> None:
    set_runtime_snapshot(
        max_concurrent=int(row.max_concurrent),
        task_timeout_minutes=int(row.task_timeout_minutes),
        chunk_parallel_enabled=bool(row.chunk_parallel_enabled),
        chunk_count=int(row.chunk_count),
        chunk_min_mb=int(row.chunk_min_mb),
    )


def _to_read(row: FetchSettingsConfig) -> FetchSettingsRead:
    return FetchSettingsRead(
        max_concurrent=int(row.max_concurrent),
        task_timeout_minutes=int(row.task_timeout_minutes),
        chunk_parallel_enabled=bool(row.chunk_parallel_enabled),
        chunk_count=int(row.chunk_count),
        chunk_min_mb=int(row.chunk_min_mb),
    )


async def get_fetch_settings(session: AsyncSession) -> FetchSettingsRead:
    row = await _ensure_row(session)
    _publish(row)
    return _to_read(row)


async def update_fetch_settings(
    session: AsyncSession, body: FetchSettingsUpdate
) -> FetchSettingsRead:
    row = await _ensure_row(session)
    row.max_concurrent = body.max_concurrent
    row.task_timeout_minutes = body.task_timeout_minutes
    row.chunk_parallel_enabled = body.chunk_parallel_enabled
    row.chunk_count = body.chunk_count
    row.chunk_min_mb = body.chunk_min_mb
    session.add(row)
    await session.commit()
    await session.refresh(row)
    _publish(row)
    return _to_read(row)
