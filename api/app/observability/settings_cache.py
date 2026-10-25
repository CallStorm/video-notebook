"""可观测开关缓存：写路径只读内存，避免每次打 DB。"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_CACHE_TTL = 8.0


@dataclass(frozen=True)
class ObsFlags:
    pipeline_logs_enabled: bool = False
    llm_traces_enabled: bool = False
    retention_days: int = 7
    success_sample_rate: float = 1.0
    llm_record_full: bool = False
    llm_truncate_chars: int = 4096
    max_pipeline_run_rows: int = 50000
    max_llm_trace_rows: int = 20000


_flags = ObsFlags()
_loaded_at = 0.0


def get_flags(*, force: bool = False) -> ObsFlags:
    global _flags, _loaded_at
    now = time.monotonic()
    if not force and (now - _loaded_at) < _CACHE_TTL:
        return _flags
    with _LOCK:
        if not force and (time.monotonic() - _loaded_at) < _CACHE_TTL:
            return _flags
        try:
            _flags = _load_sync()
        except Exception:
            logger.debug("observability settings reload failed", exc_info=True)
        _loaded_at = time.monotonic()
        return _flags


def invalidate() -> None:
    global _loaded_at
    with _LOCK:
        _loaded_at = 0.0


def _load_sync() -> ObsFlags:
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.core.config import get_settings
    from app.models.observability import ObservabilitySettingsConfig

    engine = create_engine(get_settings().database_sync_url, pool_pre_ping=True)
    try:
        with Session(engine) as session:
            row = session.get(ObservabilitySettingsConfig, 1)
            if row is None:
                return ObsFlags()
            rate = float(row.success_sample_rate or 1.0)
            rate = max(0.0, min(1.0, rate))
            trunc = int(row.llm_truncate_chars or 4096)
            trunc = max(256, min(200_000, trunc))
            return ObsFlags(
                pipeline_logs_enabled=bool(row.pipeline_logs_enabled),
                llm_traces_enabled=bool(row.llm_traces_enabled),
                retention_days=max(1, int(row.retention_days or 7)),
                success_sample_rate=rate,
                llm_record_full=bool(row.llm_record_full),
                llm_truncate_chars=trunc,
                max_pipeline_run_rows=max(1000, int(row.max_pipeline_run_rows or 50000)),
                max_llm_trace_rows=max(1000, int(row.max_llm_trace_rows or 20000)),
            )
    finally:
        engine.dispose()
