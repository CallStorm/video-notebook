"""Admin 向量配置服务。"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vector_settings import VectorSettingsConfig
from app.schemas.vector_settings import VectorSettingsRead, VectorSettingsUpdate

_ROW_ID = 1

_DEFAULTS = dict(
    vector_backend="qdrant",
    qdrant_url="http://127.0.0.1:6333",
    qdrant_api_key=None,
    qdrant_collection="notebooks",
    index_title=True,
    index_description=True,
    index_overview=True,
    index_subtitles=False,
    index_notes=False,
)


async def _ensure_row(session: AsyncSession) -> VectorSettingsConfig:
    row = await session.get(VectorSettingsConfig, _ROW_ID)
    if row is None:
        row = VectorSettingsConfig(id=_ROW_ID, **_DEFAULTS)
        session.add(row)
        await session.flush()
    return row


def _to_read(row: VectorSettingsConfig) -> VectorSettingsRead:
    key = (row.qdrant_api_key or "").strip()
    return VectorSettingsRead(
        vector_backend=row.vector_backend or "qdrant",
        qdrant_url=row.qdrant_url or "http://127.0.0.1:6333",
        qdrant_api_key=None,  # 不回传明文
        qdrant_api_key_set=bool(key),
        qdrant_collection=row.qdrant_collection or "notebooks",
        index_title=bool(row.index_title),
        index_description=bool(row.index_description),
        index_overview=bool(row.index_overview),
        index_subtitles=bool(row.index_subtitles),
        index_notes=bool(row.index_notes),
    )


async def get_vector_settings(session: AsyncSession) -> VectorSettingsRead:
    row = await _ensure_row(session)
    return _to_read(row)


async def get_vector_settings_row(session: AsyncSession) -> VectorSettingsConfig:
    return await _ensure_row(session)


async def update_vector_settings(
    session: AsyncSession, body: VectorSettingsUpdate
) -> VectorSettingsRead:
    row = await _ensure_row(session)
    row.vector_backend = (body.vector_backend or "qdrant").strip().lower() or "qdrant"
    row.qdrant_url = body.qdrant_url.strip()
    row.qdrant_collection = body.qdrant_collection.strip() or "notebooks"
    if body.clear_qdrant_api_key:
        row.qdrant_api_key = None
    elif body.qdrant_api_key is not None and body.qdrant_api_key.strip():
        row.qdrant_api_key = body.qdrant_api_key.strip()
    row.index_title = body.index_title
    row.index_description = body.index_description
    row.index_overview = body.index_overview
    row.index_subtitles = body.index_subtitles
    row.index_notes = body.index_notes
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _to_read(row)
