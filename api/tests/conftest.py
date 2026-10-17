"""共享 fixtures。

测试策略（Phase 2 起）：
- 不连真 MySQL；用 SQLite + aiosqlite（async）建内存库；
- alembic 不跑；改用 Base.metadata.create_all + drop_all；
- 这样所有测试自包含、可在没 mysql 的 CI 上跑。
"""
from __future__ import annotations

import os
import tempfile

# 测试环境变量必须在 import app.* 之前设置
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("MASTER_SECRET", "test-master-secret")
# 强制覆盖 mysql 连接 — 实际不会用到
os.environ.setdefault("MYSQL_HOST", "127.0.0.1")
os.environ.setdefault("MYSQL_USER", "root")
os.environ.setdefault("MYSQL_PASSWORD", "")
os.environ.setdefault("MYSQL_DATABASE", "test")
# 测试 storage 写到 tmpdir（避免污染真实 /data）
_TEST_STORAGE_ROOT = tempfile.mkdtemp(prefix="vnb-test-storage-")
os.environ.setdefault("STORAGE_ROOT", _TEST_STORAGE_ROOT)

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db import session as session_module  # noqa: E402
from app.db.base import Base  # noqa: E402

# 强制 import 所有 model 让 Base.metadata 注册（顺序敏感；新加 model 后这里也加 import）
from app.models.credential import Credential  # noqa: F401,E402
from app.models.default_model import DefaultModel  # noqa: F401,E402
from app.models.model import Model  # noqa: F401,E402
from app.models.notebook import (  # noqa: E402,F401
    ChatMessage,
    ChatThread,
    Note,
    Notebook,
    NotebookSource,
    Subtitle,
    SubtitleLine,
    Video,
)
from app.models.studio import (  # noqa: E402,F401
    Agent,
    Skill,
    StudioArtifact,
    StudioCapability,
    StudioTask,
)
from app.models.user import User  # noqa: F401,E402

# 重要：清掉 lru_cache 让 .env override 生效
get_settings.cache_clear()

# 强制重新构建 engine —— 指向 SQLite 内存库
# StaticPool 让所有 session 共用同一个 :memory: 连接，否则每个连接都是空库。
_TEST_DB_URL = "sqlite+aiosqlite://"
_test_engine = create_async_engine(
    _TEST_DB_URL,
    echo=False,
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
)
_test_sessionmaker = sessionmaker(
    bind=_test_engine, expire_on_commit=False, class_=AsyncSession
)

# Patch 模块级 session 工厂
session_module._engine = _test_engine
session_module._sessionmaker = _test_sessionmaker


async def _override_get_session() -> AsyncSession:  # type: ignore[override]
    async with _test_sessionmaker() as s:
        yield s


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _prepare_db():
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await _test_engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_db():
    """每个 test 后清理 users + model_configs 表，让 auth/admin_seed 不互相污染。"""

    yield
    async with _test_sessionmaker() as s:
        from sqlalchemy import text

        # 注意：SQLite 与 MySQL 都不支持多表 DELETE 在此写法；
        # 改为按依赖顺序删（model_configs 没有 FK 引用 users，可以放前面）
        for table in (
            "studio_artifacts",
            "studio_tasks",
            "studio_capabilities",
            "agents",
            "skills",
            "notes",
            "chat_messages",
            "chat_threads",
            "subtitle_lines",
            "subtitles",
            "notebook_sources",
            "videos",
            "notebooks",
            "default_models",
            "models",
            "credentials",
            "llm_configs",
            "asr_configs",
            "users",
        ):
            try:
                await s.execute(text(f"DELETE FROM {table}"))
            except Exception:
                pass
        await s.commit()


@pytest_asyncio.fixture
async def client():
    """提供 FastAPI AsyncClient，DB 依赖已 patch。"""
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[session_module.get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    async with _test_sessionmaker() as s:
        yield s
