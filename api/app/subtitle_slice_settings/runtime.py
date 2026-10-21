"""进程内缓存的语音切片设置快照（worker / ASR 切段读取）。"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

_lock = threading.Lock()
_CACHE_TTL = 5.0


@dataclass(frozen=True)
class SubtitleSliceSettingsSnapshot:
    max_slice_seconds: int = 30
    min_slice_ms: int = 600
    silence_noise_db: float = -32.0
    silence_min_duration_s: float = 0.3
    min_silence_for_cut_ms: int = 200

    @property
    def max_slice_ms(self) -> int:
        return max(1000, int(self.max_slice_seconds) * 1000)


_snapshot = SubtitleSliceSettingsSnapshot()
_loaded_at = 0.0


def set_runtime_snapshot(
    *,
    max_slice_seconds: int,
    min_slice_ms: int,
    silence_noise_db: float,
    silence_min_duration_s: float,
    min_silence_for_cut_ms: int,
) -> None:
    global _snapshot, _loaded_at
    with _lock:
        _snapshot = SubtitleSliceSettingsSnapshot(
            max_slice_seconds=max_slice_seconds,
            min_slice_ms=min_slice_ms,
            silence_noise_db=silence_noise_db,
            silence_min_duration_s=silence_min_duration_s,
            min_silence_for_cut_ms=min_silence_for_cut_ms,
        )
        _loaded_at = time.monotonic()


def invalidate_runtime_cache() -> None:
    global _loaded_at
    with _lock:
        _loaded_at = 0.0


def get_cached_settings() -> SubtitleSliceSettingsSnapshot:
    with _lock:
        return _snapshot


def get_settings_fresh() -> SubtitleSliceSettingsSnapshot:
    """Prefer cache; if stale, reload from DB (sync, for worker threads)."""
    with _lock:
        age = time.monotonic() - _loaded_at
        if _loaded_at and age < _CACHE_TTL:
            return _snapshot
    try:
        return _reload_from_db()
    except Exception:
        return get_cached_settings()


def _reload_from_db() -> SubtitleSliceSettingsSnapshot:
    import asyncio

    from app.db.session import dispose_engine, get_sessionmaker
    from app.models.subtitle_slice_settings import SubtitleSliceSettingsConfig

    async def _load() -> SubtitleSliceSettingsSnapshot:
        try:
            async with get_sessionmaker()() as session:
                row = await session.get(SubtitleSliceSettingsConfig, 1)
                if row is None:
                    snap = SubtitleSliceSettingsSnapshot()
                else:
                    snap = SubtitleSliceSettingsSnapshot(
                        max_slice_seconds=int(row.max_slice_seconds),
                        min_slice_ms=int(row.min_slice_ms),
                        silence_noise_db=float(row.silence_noise_db),
                        silence_min_duration_s=float(row.silence_min_duration_s),
                        min_silence_for_cut_ms=int(row.min_silence_for_cut_ms),
                    )
                set_runtime_snapshot(
                    max_slice_seconds=snap.max_slice_seconds,
                    min_slice_ms=snap.min_slice_ms,
                    silence_noise_db=snap.silence_noise_db,
                    silence_min_duration_s=snap.silence_min_duration_s,
                    min_silence_for_cut_ms=snap.min_silence_for_cut_ms,
                )
                return snap
        finally:
            await dispose_engine()

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_load())

    return get_cached_settings()
