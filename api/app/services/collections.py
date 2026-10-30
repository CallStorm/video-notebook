"""Collection CRUD and membership sync."""
from __future__ import annotations

import json
import re
import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.cover_url import expand_cover_url, normalize_cover_url
from app.core.errors import BadRequestError, NotFoundError
from app.models.collection import Collection, CollectionNotebook
from app.models.notebook import Notebook
from app.llm.config_service import get_active_llm
from app.llm.providers import make_provider
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
        {"id": row.id, "title": row.title, "cover_url": expand_cover_url(row.cover_url)}
        for row in rows
    ]


async def _to_read(session: AsyncSession, collection: Collection) -> dict:
    return {
        "id": collection.id,
        "name": collection.name,
        "icon": collection.icon,
        "cover_url": expand_cover_url(collection.cover_url),
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
        cover_url=normalize_cover_url(cover_url.strip() if isinstance(cover_url, str) and cover_url.strip() else None),
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
        collection.cover_url = normalize_cover_url(
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


_AUTO_ORG_SYSTEM = """你是笔记本分类助手。根据用户给出的笔记本「名称」和「描述」（没有正文），
把它们整理成若干集合（分类）。

硬性要求：
1. 集合名称用简短中文（2–8 字），贴合主题，不要编号、不要「集合1」这类空名。
2. 每个笔记本恰好属于一个集合；不要遗漏、不要重复。
3. 实在不好归类的，放入名为「未归类」的集合。
4. 集合数量要合理：笔记本少时少分几类，多时也不要超过 12 个集合。
5. 只输出严格 JSON，不要 markdown 围栏，不要解释。

JSON 格式：
{"collections":[{"name":"集合名","notebook_ids":[1,2]}]}
"""


def _extract_json_obj(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, re.IGNORECASE)
    if fence:
        raw = fence.group(1).strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(raw[start : end + 1])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            return None
    return None


def _temp_id() -> str:
    return uuid.uuid4().hex[:10]


async def _list_user_notebook_briefs(
    session: AsyncSession, user_id: int
) -> list[dict]:
    rows = (
        await session.execute(
            select(Notebook.id, Notebook.title, Notebook.description)
            .where(Notebook.owner_id == user_id, Notebook.deleted_at.is_(None))
            .order_by(Notebook.is_pinned.desc(), Notebook.id.desc())
        )
    ).all()
    return [
        {
            "id": int(row.id),
            "title": row.title or f"笔记本 {row.id}",
            "description": (row.description or "").strip() or None,
        }
        for row in rows
    ]


def _normalize_preview_plan(
    raw: dict[str, Any] | None, notebooks: list[dict]
) -> list[dict]:
    """Normalize LLM output into [{temp_id,name,notebook_ids}, ...]."""
    owned_ids = [int(n["id"]) for n in notebooks]
    owned_set = set(owned_ids)
    assigned: set[int] = set()
    out: list[dict] = []

    collections = (raw or {}).get("collections") if isinstance(raw, dict) else None
    if not isinstance(collections, list):
        collections = []

    for item in collections:
        if not isinstance(item, dict):
            continue
        name = _normalize_name(str(item.get("name") or "未命名"))
        ids_raw = item.get("notebook_ids") or item.get("notebookIds") or []
        if not isinstance(ids_raw, list):
            continue
        ids: list[int] = []
        for x in ids_raw:
            try:
                nid = int(x)
            except (TypeError, ValueError):
                continue
            if nid in owned_set and nid not in assigned:
                ids.append(nid)
                assigned.add(nid)
        if not ids and name == "未归类":
            continue
        out.append({"temp_id": _temp_id(), "name": name, "notebook_ids": ids})

    missing = [nid for nid in owned_ids if nid not in assigned]
    if missing:
        # merge into existing 未归类 or create one
        uncategorized = next((c for c in out if c["name"] == "未归类"), None)
        if uncategorized is None:
            out.append(
                {"temp_id": _temp_id(), "name": "未归类", "notebook_ids": missing}
            )
        else:
            uncategorized["notebook_ids"].extend(missing)

    # drop empty collections except keep at least one if we have notebooks
    out = [c for c in out if c["notebook_ids"]]
    if not out and owned_ids:
        out = [
            {
                "temp_id": _temp_id(),
                "name": "未归类",
                "notebook_ids": list(owned_ids),
            }
        ]
    return out


async def preview_auto_organize(session: AsyncSession, user_id: int) -> dict:
    notebooks = await _list_user_notebook_briefs(session, user_id)
    if not notebooks:
        return {
            "collections": [],
            "notebooks": [],
            "message": "没有可整理的笔记本",
        }

    payload = [
        {
            "id": n["id"],
            "title": n["title"],
            "description": n["description"] or "",
        }
        for n in notebooks
    ]
    user_prompt = (
        "请根据下列笔记本的名称与描述生成集合分类方案。\n\n"
        + json.dumps(payload, ensure_ascii=False)
    )

    try:
        llm = await get_active_llm(session)
        provider = make_provider(
            provider_name=llm.provider,
            api_key=llm.api_key,
            base_url=llm.base_url,
            model_name=llm.model_name,
            params_json=llm.params_json,
        )
        raw_text = await provider.complete(
            user_prompt,
            system=_AUTO_ORG_SYSTEM,
            max_tokens=4096,
            temperature=0.3,
        )
        parsed = _extract_json_obj(raw_text)
        if parsed is None:
            # heuristic fallback: one collection per keyword-ish title prefix
            parsed = {
                "collections": [
                    {
                        "name": "未归类",
                        "notebook_ids": [n["id"] for n in notebooks],
                    }
                ]
            }
            message = "模型返回无法解析，已给出兜底方案，请手工调整"
        else:
            message = None
    except Exception as exc:  # noqa: BLE001 — surface as soft fallback
        parsed = {
            "collections": [
                {
                    "name": "未归类",
                    "notebook_ids": [n["id"] for n in notebooks],
                }
            ]
        }
        message = f"分析失败（{exc}），已给出兜底方案，请手工调整"

    plan = _normalize_preview_plan(parsed, notebooks)
    return {
        "collections": plan,
        "notebooks": notebooks,
        "message": message,
    }


def _validate_apply_plan(
    collections: list[dict], owned_ids: set[int]
) -> list[dict]:
    if not collections:
        raise BadRequestError("方案不能为空")
    seen: set[int] = set()
    cleaned: list[dict] = []
    for item in collections:
        name = _normalize_name(str(item.get("name") or ""))
        ids_raw = item.get("notebook_ids") or []
        if not isinstance(ids_raw, list):
            raise BadRequestError("notebook_ids 格式错误")
        ids: list[int] = []
        for x in ids_raw:
            try:
                nid = int(x)
            except (TypeError, ValueError) as exc:
                raise BadRequestError("notebook_ids 含无效值") from exc
            if nid not in owned_ids:
                raise BadRequestError(f"笔记本无效: {nid}")
            if nid in seen:
                raise BadRequestError(f"笔记本重复归属: {nid}")
            seen.add(nid)
            ids.append(nid)
        cleaned.append({"name": name, "notebook_ids": ids})

    missing = sorted(owned_ids - seen)
    if missing:
        uncategorized = next((c for c in cleaned if c["name"] == "未归类"), None)
        if uncategorized is None:
            cleaned.append({"name": "未归类", "notebook_ids": missing})
        else:
            uncategorized["notebook_ids"].extend(missing)

    # allow empty collections to be dropped
    cleaned = [c for c in cleaned if c["notebook_ids"] or c["name"] == "未归类"]
    cleaned = [c for c in cleaned if c["notebook_ids"]]
    if not cleaned and owned_ids:
        cleaned = [{"name": "未归类", "notebook_ids": sorted(owned_ids)}]
    if not cleaned:
        raise BadRequestError("没有可写入的集合")
    return cleaned


async def apply_auto_organize(
    session: AsyncSession, user_id: int, collections_in: list[dict]
) -> list[dict]:
    notebooks = await _list_user_notebook_briefs(session, user_id)
    owned_ids = {int(n["id"]) for n in notebooks}
    plan = _validate_apply_plan(collections_in, owned_ids)

    # Load existing collections for this user
    existing = (
        await session.execute(
            select(Collection).where(Collection.owner_id == user_id)
        )
    ).scalars().all()
    existing_ids = [c.id for c in existing]

    try:
        if existing_ids:
            await session.execute(
                delete(CollectionNotebook).where(
                    CollectionNotebook.collection_id.in_(existing_ids)
                )
            )
            await session.execute(
                delete(Collection).where(Collection.id.in_(existing_ids))
            )

        created_reads: list[dict] = []
        for item in plan:
            collection = Collection(
                owner_id=user_id,
                name=item["name"],
                icon=None,
                cover_url=None,
            )
            session.add(collection)
            await session.flush()
            for notebook_id in item["notebook_ids"]:
                session.add(
                    CollectionNotebook(
                        collection_id=collection.id, notebook_id=notebook_id
                    )
                )
            created_reads.append(collection)

        await session.commit()
        # refresh reads after commit
        result = []
        for collection in created_reads:
            await session.refresh(collection)
            result.append(await _to_read(session, collection))
        return result
    except Exception:
        await session.rollback()
        raise

