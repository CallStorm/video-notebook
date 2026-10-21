"""异步 session 工厂 + 依赖注入。

用法：
    async def endpoint(session: AsyncSession = Depends(get_session)):
        ...

Celery thread pool 下每个线程各自持有 AsyncEngine，避免跨 event loop 复用。
"""
from __future__ import annotations

import threading
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

_local = threading.local()


def _build_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=settings.debug,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


def get_engine() -> AsyncEngine:
    engine = getattr(_local, "engine", None)
    if engine is None:
        engine = _build_engine()
        _local.engine = engine
    return engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    sm = getattr(_local, "sessionmaker", None)
    if sm is None:
        sm = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            class_=AsyncSession,
        )
        _local.sessionmaker = sm
    return sm


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖：每个请求拿一个新 session。"""
    sm = get_sessionmaker()
    async with sm() as session:
        yield session


async def dispose_engine() -> None:
    engine = getattr(_local, "engine", None)
    if engine is not None:
        await engine.dispose()
    _local.engine = None
    _local.sessionmaker = None


def clear_engine_sync() -> None:
    """同步清空本线程的 engine 引用（不 dispose；供 Celery 开新 loop 前调用）。"""
    _local.engine = None
    _local.sessionmaker = None
