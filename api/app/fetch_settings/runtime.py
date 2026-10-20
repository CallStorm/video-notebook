"""进程内缓存的抓取设置快照（worker / yt-dlp 读取）。"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

_lock = threading.Lock()
_CACHE_TTL = 5.0


@dataclass(frozen=True)
class FetchSettingsSnapshot:
    max_concurrent: int = 2
    task_timeout_minutes: int = 30
    chunk_parallel_enabled: bool = True
    chunk_count: int = 4
    chunk_min_mb: int = 20

    @property
    def task_timeout_seconds(self) -> int:
        return max(60, int(self.task_timeout_minutes) * 60)

    @property
    def soft_time_limit(self) -> int:
        hard = self.task_timeout_seconds
        return max(30, hard - 60)

    @property
    def hard_time_limit(self) -> int:
        return self.task_timeout_seconds


_snapshot = FetchSettingsSnapshot()
_loaded_at = 0.0


def set_runtime_snapshot(
    *,
    max_concurrent: int,
    task_timeout_minutes: int,
    chunk_parallel_enabled: bool,
    chunk_count: int,
    chunk_min_mb: int,
) -> None:
    global _snapshot, _loaded_at
    with _lock:
        _snapshot = FetchSettingsSnapshot(
            max_concurrent=max_concurrent,
            task_timeout_minutes=task_timeout_minutes,
            chunk_parallel_enabled=chunk_parallel_enabled,
            chunk_count=chunk_count,
            chunk_min_mb=chunk_min_mb,
        )
        _loaded_at = time.monotonic()


def invalidate_runtime_cache() -> None:
    global _loaded_at
    with _lock:
        _loaded_at = 0.0


def get_cached_settings() -> FetchSettingsSnapshot:
    with _lock:
        return _snapshot


def get_settings_fresh() -> FetchSettingsSnapshot:
    """Prefer cache; if stale, reload from DB (sync, for worker threads)."""
    with _lock:
        age = time.monotonic() - _loaded_at
        if _loaded_at and age < _CACHE_TTL:
            return _snapshot
    try:
        return _reload_from_db()
    except Exception:
        return get_cached_settings()


def _reload_from_db() -> FetchSettingsSnapshot:
    import asyncio

    from app.db.session import dispose_engine, get_sessionmaker
    from app.models.fetch_settings import FetchSettingsConfig

    async def _load() -> FetchSettingsSnapshot:
        try:
            async with get_sessionmaker()() as session:
                row = await session.get(FetchSettingsConfig, 1)
                if row is None:
                    snap = FetchSettingsSnapshot()
                else:
                    snap = FetchSettingsSnapshot(
                        max_concurrent=int(row.max_concurrent),
                        task_timeout_minutes=int(row.task_timeout_minutes),
                        chunk_parallel_enabled=bool(row.chunk_parallel_enabled),
                        chunk_count=int(row.chunk_count),
                        chunk_min_mb=int(row.chunk_min_mb),
                    )
                set_runtime_snapshot(
                    max_concurrent=snap.max_concurrent,
                    task_timeout_minutes=snap.task_timeout_minutes,
                    chunk_parallel_enabled=snap.chunk_parallel_enabled,
                    chunk_count=snap.chunk_count,
                    chunk_min_mb=snap.chunk_min_mb,
                )
                return snap
        finally:
            # Avoid leaving an AsyncEngine bound to this short-lived loop
            # (Celery thread pool would then hit "Future attached to a different loop").
            await dispose_engine()

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_load())

    # Already in async loop: return cache / defaults without nesting asyncio.run
    return get_cached_settings()


def apply_chunk_opts(opts: dict, *, filesize: int | None = None) -> dict:
    """Inject yt-dlp concurrent_fragment_downloads from settings."""
    snap = get_settings_fresh()
    out = dict(opts)
    if not snap.chunk_parallel_enabled:
        out["concurrent_fragment_downloads"] = 1
        return out
    min_bytes = snap.chunk_min_mb * 1024 * 1024
    if filesize is not None and filesize > 0 and filesize < min_bytes:
        out["concurrent_fragment_downloads"] = 1
    else:
        out["concurrent_fragment_downloads"] = max(1, int(snap.chunk_count))
    return out
