"""FastAPI 应用入口。

启动行为：
1. configure_logging() — JSON 行日志
2. 注册全局异常处理器（errors.AppError / RequestValidationError）
3. 挂载 /api 路由组（含 /api/health, /api/auth/*, /api/users/me, /api/admin/*）
4. lifespan: 释放 DB 引擎 + 跑 admin seed（Phase 2）
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.admin_seed import seed_admin_if_empty
from app.core.config import get_settings
from app.core.errors import AppError, app_error_handler, validation_error_handler
from app.core.logging import configure_logging, get_logger
from app.db.session import dispose_engine, get_sessionmaker
from app.routes import api_router
from app.services.capabilities import seed_builtin_capabilities

configure_logging()
logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info(
        "api starting",
        extra={"env": settings.app_env, "debug": settings.debug},
    )
    await seed_admin_if_empty()
    if settings.app_env != "test":
        async with get_sessionmaker()() as session:
            await seed_builtin_capabilities(session)
    try:
        yield
    finally:
        await dispose_engine()
        logger.info("api stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"service": settings.app_name, "api_prefix": settings.api_prefix}

    return app


app = create_app()
