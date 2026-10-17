"""GET /api/health — 容器存活 / 依赖检查。"""
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.core.logging import get_logger
from app.db.session import get_sessionmaker

router = APIRouter(tags=["meta"])
logger = get_logger(__name__)


@router.get("/health")
async def health() -> dict[str, str]:
    """基础存活检查：进程能应答。"""
    return {"status": "ok"}


@router.get("/health/ready")
async def health_ready() -> dict[str, object]:
    """就绪检查：异步尝试一次 DB ping。失败 → 503（生产可做；当前保留为手动切换）。"""
    sm = get_sessionmaker()
    try:
        async with sm() as session:
            await session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:  # noqa: BLE001 — 探针性接口允许吞
        logger.warning("health_ready db ping failed", extra={"err": str(exc)})
        db_status = f"down: {type(exc).__name__}"
    return {"status": "ok" if db_status == "ok" else "degraded", "db": db_status}
