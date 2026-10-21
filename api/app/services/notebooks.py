"""Notebook CRUD 服务。

多租户隔离：所有查询过滤 owner_id；admin 也只能看自己的 notebook。
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.notebook import Note, Notebook, NotebookSource, Video
from app.models.user import User
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


def _to_read_dict(
    nb: Notebook,
    source_count: int = 0,
    note_count: int = 0,
    *,
    owner_name: str | None = None,
    viewer_id: int | None = None,
) -> dict:
    return {
        "id": nb.id,
        "title": nb.title,
        "description": nb.description,
        "icon": nb.icon,
        "cover_url": nb.cover_url,
        "is_pinned": nb.is_pinned,
        "share_all": nb.share_all,
        "owner_id": nb.owner_id,
        "owner_name": owner_name,
        "is_owner": (viewer_id == nb.owner_id) if viewer_id is not None else None,
        "source_count": source_count,
        "note_count": note_count,
        "created_at": nb.created_at.isoformat() if nb.created_at else None,
        "updated_at": nb.updated_at.isoformat() if nb.updated_at else None,
    }


def can_read_notebook(nb: Notebook, viewer_id: int) -> bool:
    """主人可读；开启 share_all 的未删除本，任意登录用户可读。"""
    if nb.deleted_at is not None:
        return False
    if nb.owner_id == viewer_id:
        return True
    return bool(nb.share_all)



async def counts_for_notebooks(
    session: AsyncSession, notebook_ids: list[int]
) -> dict[int, tuple[int, int]]:
    """批量统计每个 notebook 的来源数与笔记数（笔记排除软删除）。"""
    if not notebook_ids:
        return {}
    source_rows = (
        await session.execute(
            select(NotebookSource.notebook_id, func.count())
            .where(NotebookSource.notebook_id.in_(notebook_ids))
            .group_by(NotebookSource.notebook_id)
        )
    ).all()
    note_rows = (
        await session.execute(
            select(Note.notebook_id, func.count())
            .where(Note.notebook_id.in_(notebook_ids), Note.deleted_at.is_(None))
            .group_by(Note.notebook_id)
        )
    ).all()
    source_map = {int(nid): int(cnt) for nid, cnt in source_rows}
    note_map = {int(nid): int(cnt) for nid, cnt in note_rows}
    return {
        int(nid): (source_map.get(int(nid), 0), note_map.get(int(nid), 0))
        for nid in notebook_ids
    }


async def _owner_names(session: AsyncSession, owner_ids: list[int]) -> dict[int, str]:
    ids = sorted({int(i) for i in owner_ids if i is not None})
    if not ids:
        return {}
    rows = (
        await session.execute(select(User.id, User.name).where(User.id.in_(ids)))
    ).all()
    return {int(uid): name for uid, name in rows}


async def to_read(
    session: AsyncSession,
    nb: Notebook,
    *,
    viewer_id: int | None = None,
    include_owner_name: bool = False,
) -> dict:
    counts = await counts_for_notebooks(session, [nb.id])
    source_count, note_count = counts.get(nb.id, (0, 0))
    owner_name = None
    if include_owner_name:
        names = await _owner_names(session, [nb.owner_id])
        owner_name = names.get(nb.owner_id)
    return _to_read_dict(
        nb,
        source_count=source_count,
        note_count=note_count,
        owner_name=owner_name,
        viewer_id=viewer_id,
    )


async def to_read_many(
    session: AsyncSession,
    notebooks: list[Notebook],
    *,
    viewer_id: int | None = None,
    include_owner_name: bool = False,
) -> list[dict]:
    counts = await counts_for_notebooks(session, [nb.id for nb in notebooks])
    names: dict[int, str] = {}
    if include_owner_name:
        names = await _owner_names(session, [nb.owner_id for nb in notebooks])
    out: list[dict] = []
    for nb in notebooks:
        source_count, note_count = counts.get(nb.id, (0, 0))
        out.append(
            _to_read_dict(
                nb,
                source_count=source_count,
                note_count=note_count,
                owner_name=names.get(nb.owner_id),
                viewer_id=viewer_id,
            )
        )
    return out


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
    """仅主人。写操作 / 隔离查询继续用这个。"""
    nb = await session.get(Notebook, notebook_id)
    if nb is None or nb.owner_id != owner_id or nb.deleted_at is not None:
        raise NotFoundError(f"notebook {notebook_id} 不存在")
    return nb


async def get_notebook_readable(
    session: AsyncSession, *, viewer_id: int, notebook_id: int
) -> Notebook:
    """主人，或 share_all=True 的公开本。"""
    nb = await session.get(Notebook, notebook_id)
    if nb is None or not can_read_notebook(nb, viewer_id):
        raise NotFoundError(f"notebook {notebook_id} 不存在")
    return nb


async def list_shared_notebooks(
    session: AsyncSession,
    *,
    viewer_id: int,
    page: int,
    size: int,
) -> tuple[list[Notebook], int]:
    """发现页：其他人开启 share_all 的笔记本（不含自己的）。"""
    stmt = select(Notebook).where(
        Notebook.share_all.is_(True),
        Notebook.deleted_at.is_(None),
        Notebook.owner_id != viewer_id,
    )
    total = (
        await session.scalar(select(func.count()).select_from(stmt.subquery()))
    ) or 0
    stmt = (
        stmt.order_by(Notebook.updated_at.desc(), Notebook.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    items = (await session.execute(stmt)).scalars().all()
    return list(items), int(total)


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
    return await to_read(session, nb)


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
    return await to_read(session, nb)


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
    return await to_read(session, nb)


async def list_sources(
    session: AsyncSession, *, owner_id: int, notebook_id: int
) -> list[SourceSummary]:
    """兼容旧调用：按主人身份列来源。"""
    nb = await get_notebook(session, owner_id=owner_id, notebook_id=notebook_id)
    return await list_sources_for_notebook(session, notebook=nb)


async def list_sources_readable(
    session: AsyncSession, *, viewer_id: int, notebook_id: int
) -> list[SourceSummary]:
    nb = await get_notebook_readable(
        session, viewer_id=viewer_id, notebook_id=notebook_id
    )
    return await list_sources_for_notebook(session, notebook=nb)


async def list_sources_for_notebook(
    session: AsyncSession, *, notebook: Notebook
) -> list[SourceSummary]:
    stmt = (
        select(NotebookSource, Video)
        .join(Video, Video.id == NotebookSource.video_id)
        .where(NotebookSource.notebook_id == notebook.id)
        .order_by(NotebookSource.sort, NotebookSource.video_id)
    )
    rows = (await session.execute(stmt)).all()
    summaries: list[SourceSummary] = []
    for ns, v in rows:
        # 只展示笔记本主人名下的视频，避免脏关联泄漏
        if v.owner_id != notebook.owner_id:
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
