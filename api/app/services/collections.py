"""Collection CRUD and membership sync."""
from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, NotFoundError
from app.models.collection import Collection, CollectionNotebook
from app.models.notebook import Notebook
from app.services import notebooks as notebook_svc


def _normalize_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise BadRequestError("名称不能为空")
    return cleaned[:255]


def _dt(value) -> str | None:
    return value.isoformat() if value else None


async def _notebook_count(session: AsyncSession, collection_id: int) -> int:
    stmt = (
        select(func.count())
        .select_from(CollectionNotebook)
        .join(Notebook, Notebook.id == CollectionNotebook.notebook_id)
        .where(
            CollectionNotebook.collection_id == collection_id,
            Notebook.deleted_at.is_(None),
        )
    )
    return int((await session.scalar(stmt)) or 0)


async def _preview_notebooks(
    session: AsyncSession, collection_id: int, *, limit: int = 24
) -> list[dict]:
    rows = (
        await session.execute(
            select(Notebook.id, Notebook.title, Notebook.cover_url)
            .join(CollectionNotebook, CollectionNotebook.notebook_id == Notebook.id)
            .where(
                CollectionNotebook.collection_id == collection_id,
                Notebook.deleted_at.is_(None),
            )
            .order_by(Notebook.is_pinned.desc(), Notebook.id.desc())
            .limit(limit)
        )
    ).all()
    return [
        {"id": row.id, "title": row.title, "cover_url": row.cover_url}
        for row in rows
    ]


async def _to_read(session: AsyncSession, collection: Collection) -> dict:
    return {
        "id": collection.id,
        "name": collection.name,
        "icon": collection.icon,
        "cover_url": collection.cover_url,
        "notebook_count": await _notebook_count(session, collection.id),
        "preview_notebooks": await _preview_notebooks(session, collection.id),
        "created_at": _dt(collection.created_at),
        "updated_at": _dt(collection.updated_at),
    }


async def get_owned_collection(
    session: AsyncSession, user_id: int, collection_id: int
) -> Collection:
    collection = await session.get(Collection, collection_id)
    if collection is None or collection.owner_id != user_id:
        raise NotFoundError("集合不存在")
    return collection


async def list_collections(session: AsyncSession, user_id: int) -> list[dict]:
    rows = (
        await session.execute(
            select(Collection)
            .where(Collection.owner_id == user_id)
            .order_by(Collection.id.desc())
        )
    ).scalars().all()
    return [await _to_read(session, row) for row in rows]


async def create_collection(
    session: AsyncSession,
    user_id: int,
    *,
    name: str,
    icon: str | None = None,
    cover_url: str | None = None,
) -> dict:
    collection = Collection(
        owner_id=user_id,
        name=_normalize_name(name),
        icon=(icon.strip() if isinstance(icon, str) and icon.strip() else None),
        cover_url=(cover_url.strip() if isinstance(cover_url, str) and cover_url.strip() else None),
    )
    session.add(collection)
    await session.commit()
    await session.refresh(collection)
    return await _to_read(session, collection)


async def get_collection(session: AsyncSession, user_id: int, collection_id: int) -> dict:
    collection = await get_owned_collection(session, user_id, collection_id)
    detail = await _to_read(session, collection)
    notebooks = await _list_member_notebooks(session, collection.id)
    detail["notebooks"] = notebooks
    return detail


async def _list_member_notebooks(session: AsyncSession, collection_id: int) -> list[dict]:
    rows = (
        await session.execute(
            select(Notebook)
            .join(CollectionNotebook, CollectionNotebook.notebook_id == Notebook.id)
            .where(
                CollectionNotebook.collection_id == collection_id,
                Notebook.deleted_at.is_(None),
            )
            .order_by(Notebook.is_pinned.desc(), Notebook.id.desc())
        )
    ).scalars().all()
    return await notebook_svc.to_read_many(session, list(rows))


async def update_collection(
    session: AsyncSession,
    user_id: int,
    collection_id: int,
    *,
    name: str | None = None,
    icon_provided: bool = False,
    icon: str | None = None,
    cover_url_provided: bool = False,
    cover_url: str | None = None,
) -> dict:
    collection = await get_owned_collection(session, user_id, collection_id)
    if name is not None:
        collection.name = _normalize_name(name)
    if icon_provided:
        collection.icon = icon.strip() if isinstance(icon, str) and icon.strip() else None
    if cover_url_provided:
        collection.cover_url = (
            cover_url.strip() if isinstance(cover_url, str) and cover_url.strip() else None
        )
    session.add(collection)
    await session.commit()
    await session.refresh(collection)
    return await _to_read(session, collection)


async def delete_collection(session: AsyncSession, user_id: int, collection_id: int) -> None:
    collection = await get_owned_collection(session, user_id, collection_id)
    await session.delete(collection)
    await session.commit()


async def set_collection_notebooks(
    session: AsyncSession,
    user_id: int,
    collection_id: int,
    notebook_ids: list[int],
) -> dict:
    collection = await get_owned_collection(session, user_id, collection_id)
    unique_ids = list(dict.fromkeys(notebook_ids))
    if unique_ids:
        owned = (
            await session.execute(
                select(Notebook.id).where(
                    Notebook.owner_id == user_id,
                    Notebook.deleted_at.is_(None),
                    Notebook.id.in_(unique_ids),
                )
            )
        ).scalars().all()
        if set(owned) != set(unique_ids):
            raise BadRequestError("笔记本无效")
    await session.execute(
        delete(CollectionNotebook).where(CollectionNotebook.collection_id == collection.id)
    )
    for notebook_id in unique_ids:
        session.add(
            CollectionNotebook(collection_id=collection.id, notebook_id=notebook_id)
        )
    await session.commit()
    return await get_collection(session, user_id, collection.id)


async def get_notebook_collection_ids(
    session: AsyncSession, user_id: int, notebook_id: int
) -> list[int]:
    await notebook_svc.get_notebook(session, owner_id=user_id, notebook_id=notebook_id)
    rows = (
        await session.execute(
            select(CollectionNotebook.collection_id)
            .join(Collection, Collection.id == CollectionNotebook.collection_id)
            .where(
                CollectionNotebook.notebook_id == notebook_id,
                Collection.owner_id == user_id,
            )
            .order_by(CollectionNotebook.collection_id.asc())
        )
    ).scalars().all()
    return list(rows)


async def set_notebook_collections(
    session: AsyncSession,
    user_id: int,
    notebook_id: int,
    collection_ids: list[int],
) -> list[int]:
    await notebook_svc.get_notebook(session, owner_id=user_id, notebook_id=notebook_id)
    unique_ids = list(dict.fromkeys(collection_ids))
    if unique_ids:
        owned = (
            await session.execute(
                select(Collection.id).where(
                    Collection.owner_id == user_id,
                    Collection.id.in_(unique_ids),
                )
            )
        ).scalars().all()
        if set(owned) != set(unique_ids):
            raise BadRequestError("集合无效")
    await session.execute(
        delete(CollectionNotebook).where(CollectionNotebook.notebook_id == notebook_id)
    )
    for collection_id in unique_ids:
        session.add(
            CollectionNotebook(collection_id=collection_id, notebook_id=notebook_id)
        )
    await session.commit()
    return await get_notebook_collection_ids(session, user_id, notebook_id)
