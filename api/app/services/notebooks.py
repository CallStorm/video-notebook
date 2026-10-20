"""Notebook CRUD 服务。

多租户隔离：所有查询过滤 owner_id；admin 也只能看自己的 notebook。
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.notebook import Notebook, NotebookSource, Video
from app.schemas.notebook import SourceSummary


def _video_to_dict(v: Video) -> dict:
    return {
        "id": v.id,
        "source_type": v.source_type,
        "source_url": v.source_url,
        "storage_key": v.storage_key,
        "mime": v.mime,
        "duration_ms": v.duration_ms,
        "width": v.width,
        "height": v.height,
        "size_bytes": v.size_bytes,
        "content_hash": v.content_hash,
        "status": v.status,
        "error_message": v.error_message,
        "subtitle_status": v.subtitle_status,
        "subtitle_error": v.subtitle_error,
        "overview_status": v.overview_status,
        "overview_text": v.overview_text,
        "overview_error": v.overview_error,
        "title": v.title,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "updated_at": v.updated_at.isoformat() if v.updated_at else None,
    }


def _to_read_dict(nb: Notebook, source_count: int = 0, note_count: int = 0) -> dict:
    return {
        "id": nb.id,
        "title": nb.title,
        "description": nb.description,
        "icon": nb.icon,
        "cover_url": nb.cover_url,
        "is_pinned": nb.is_pinned,
        "share_all": nb.share_all,
        "source_count": source_count,
        "note_count": note_count,
        "created_at": nb.created_at.isoformat() if nb.created_at else None,
        "updated_at": nb.updated_at.isoformat() if nb.updated_at else None,
    }


async def list_notebooks(
    session: AsyncSession,
    *,
    owner_id: int,
    search: str | None,
    page: int,
    size: int,
) -> tuple[list[Notebook], int]:
    stmt = select(Notebook).where(Notebook.owner_id == owner_id, Notebook.deleted_at.is_(None))
    if search:
        like = f"%{search}%"
        stmt = stmt.where(Notebook.title.like(like))
    total = (
        await session.scalar(
            select(func.count()).select_from(stmt.subquery())
        )
    ) or 0
    stmt = stmt.order_by(Notebook.is_pinned.desc(), Notebook.id.desc()).offset(
        (page - 1) * size
    ).limit(size)
    items = (await session.execute(stmt)).scalars().all()
    return list(items), int(total)


async def get_notebook(
    session: AsyncSession, *, owner_id: int, notebook_id: int
) -> Notebook:
    nb = await session.get(Notebook, notebook_id)
    if nb is None or nb.owner_id != owner_id or nb.deleted_at is not None:
        raise NotFoundError(f"notebook {notebook_id} 不存在")
    return nb


async def create_notebook(
    session: AsyncSession,
    *,
    owner_id: int,
    title: str,
    description: str | None = None,
    icon: str | None = None,
    cover_url: str | None = None,
) -> dict:
    nb = Notebook(
        owner_id=owner_id,
        title=title,
        description=description,
        icon=icon,
        cover_url=cover_url,
        is_pinned=False,
        share_all=False,
    )
    session.add(nb)
    await session.commit()
    await session.refresh(nb)
    return _to_read_dict(nb)


async def update_notebook(
    session: AsyncSession,
    *,
    owner_id: int,
    notebook_id: int,
    title: str | None = None,
    description: str | None = None,
    icon: str | None = None,
    cover_url: str | None = None,
    cover_url_set: bool = False,
    is_pinned: bool | None = None,
) -> dict:
    nb = await get_notebook(session, owner_id=owner_id, notebook_id=notebook_id)
    if title is not None:
        nb.title = title
    if description is not None:
        nb.description = description
    if icon is not None:
        nb.icon = icon
    if cover_url_set:
        nb.cover_url = cover_url
    if is_pinned is not None:
        nb.is_pinned = is_pinned
    session.add(nb)
    await session.commit()
    await session.refresh(nb)
    return _to_read_dict(nb)


async def delete_notebook(
    session: AsyncSession, *, owner_id: int, notebook_id: int
) -> None:
    nb = await get_notebook(session, owner_id=owner_id, notebook_id=notebook_id)
    nb.deleted_at = datetime.now(UTC)
    session.add(nb)
    await session.commit()


async def set_share_all(
    session: AsyncSession,
    *,
    owner_id: int,
    notebook_id: int,
    value: bool,
) -> dict:
    nb = await get_notebook(session, owner_id=owner_id, notebook_id=notebook_id)
    nb.share_all = value
    session.add(nb)
    await session.commit()
    await session.refresh(nb)
    return _to_read_dict(nb)


async def list_sources(
    session: AsyncSession, *, owner_id: int, notebook_id: int
) -> list[SourceSummary]:
    await get_notebook(session, owner_id=owner_id, notebook_id=notebook_id)
    stmt = (
        select(NotebookSource, Video)
        .join(Video, Video.id == NotebookSource.video_id)
        .where(NotebookSource.notebook_id == notebook_id)
        .order_by(NotebookSource.sort, NotebookSource.video_id)
    )
    rows = (await session.execute(stmt)).all()
    summaries: list[SourceSummary] = []
    for ns, v in rows:
        if v.owner_id != owner_id:
            continue
        summaries.append(
            SourceSummary(
                notebook_id=ns.notebook_id,
                video_id=ns.video_id,
                sort=ns.sort,
                selected_for_chat=ns.selected_for_chat,
                video=_video_to_dict(v),
            )
        )
    return summaries
