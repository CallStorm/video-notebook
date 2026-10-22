"""/api/admin/vector-settings — 向量后端与索引字段。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_session
from app.models.notebook import Notebook
from app.models.user import User
from app.schemas.vector_settings import (
    VectorReindexAllResult,
    VectorSettingsRead,
    VectorSettingsUpdate,
)
from app.services import vector_settings as svc
from app.vector.enqueue import enqueue_index_notebook

router = APIRouter(prefix="/admin/vector-settings", tags=["admin-vector-settings"])


@router.get("", response_model=VectorSettingsRead)
async def get_vector_settings(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.get_vector_settings(session)


@router.put("", response_model=VectorSettingsRead)
async def put_vector_settings(
    body: VectorSettingsUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    return await svc.update_vector_settings(session, body)


@router.post("/reindex-all", response_model=VectorReindexAllResult)
async def reindex_all(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
):
    """全量重建：给所有未删除笔记本排队索引。"""
    ids = (
        await session.execute(
            select(Notebook.id).where(Notebook.deleted_at.is_(None)).order_by(Notebook.id)
        )
    ).scalars().all()
    queued = 0
    for nid in ids:
        enqueue_index_notebook(int(nid), force=True)
        queued += 1
    return VectorReindexAllResult(
        queued=queued,
        message=f"已排队 {queued} 本笔记本重新索引（需 media-worker 在跑）",
    )
