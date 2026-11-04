"""Admin 向量配置服务。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notebook import Notebook
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
    index_subtitles=True,
    index_notes=True,
    index_conclusions=True,
    index_draft=True,
    chunk_card_chars=6000,
    chunk_subtitles_chars=6000,
    chunk_notes_chars=6000,
    chunk_conclusions_chars=6000,
    chunk_draft_chars=6000,
    chunk_overlap_chars=200,
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
        index_conclusions=bool(row.index_conclusions),
        index_draft=bool(row.index_draft),
        chunk_card_chars=int(row.chunk_card_chars or 6000),
        chunk_subtitles_chars=int(row.chunk_subtitles_chars or 6000),
        chunk_notes_chars=int(row.chunk_notes_chars or 6000),
        chunk_conclusions_chars=int(row.chunk_conclusions_chars or 6000),
        chunk_draft_chars=int(row.chunk_draft_chars or 6000),
        chunk_overlap_chars=int(
            200 if row.chunk_overlap_chars is None else row.chunk_overlap_chars
        ),
    )


async def get_vector_settings(session: AsyncSession) -> VectorSettingsRead:
    row = await _ensure_row(session)
    return _to_read(row)


async def get_vector_settings_row(session: AsyncSession) -> VectorSettingsConfig:
    return await _ensure_row(session)


def _index_flags(row: VectorSettingsConfig) -> tuple[int, ...]:
    return (
        int(bool(row.index_title)),
        int(bool(row.index_description)),
        int(bool(row.index_overview)),
        int(bool(row.index_subtitles)),
        int(bool(row.index_notes)),
        int(bool(row.index_conclusions)),
        int(bool(row.index_draft)),
        int(row.chunk_card_chars or 6000),
        int(row.chunk_subtitles_chars or 6000),
        int(row.chunk_notes_chars or 6000),
        int(row.chunk_conclusions_chars or 6000),
        int(row.chunk_draft_chars or 6000),
        int(200 if row.chunk_overlap_chars is None else row.chunk_overlap_chars),
    )


async def update_vector_settings(
    session: AsyncSession, body: VectorSettingsUpdate
) -> VectorSettingsRead:
    row = await _ensure_row(session)
    before = _index_flags(row)
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
    row.index_conclusions = body.index_conclusions
    row.index_draft = body.index_draft
    row.chunk_card_chars = body.chunk_card_chars
    row.chunk_subtitles_chars = body.chunk_subtitles_chars
    row.chunk_notes_chars = body.chunk_notes_chars
    row.chunk_conclusions_chars = body.chunk_conclusions_chars
    row.chunk_draft_chars = body.chunk_draft_chars
    row.chunk_overlap_chars = body.chunk_overlap_chars
    changed = _index_flags(row) != before
    session.add(row)
    await session.commit()
    await session.refresh(row)
    if changed:
        await _schedule_live_notebooks(session)
    return _to_read(row)


async def _schedule_live_notebooks(session: AsyncSession) -> None:
    from app.vector.schedule import touch_notebook_index

    ids = (
        await session.scalars(
            select(Notebook.id).where(Notebook.deleted_at.is_(None)).order_by(Notebook.id)
        )
    ).all()
    for nid in ids:
        touch_notebook_index(int(nid))
