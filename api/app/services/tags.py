"""Tag CRUD, membership, and AI auto-organize."""
from __future__ import annotations

import json
import re
import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, NotFoundError
from app.llm.config_service import get_active_llm
from app.llm.providers import make_provider
from app.models.notebook import Notebook
from app.models.tag import NotebookTag, Tag
from app.observability import end_llm_trace, llm_span, start_llm_trace
from app.services import notebooks as notebook_svc

DEFAULT_COLORS = [
    "#2F6B4F",
    "#3B82F6",
    "#8B5CF6",
    "#F59E0B",
    "#EF4444",
    "#06B6D4",
    "#EC4899",
    "#84CC16",
]


def _normalize_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise BadRequestError("名称不能为空")
    return cleaned[:64]


def _normalize_color(color: str | None) -> str | None:
    if color is None:
        return None
    if not isinstance(color, str):
        return None
    cleaned = color.strip()
    if not cleaned:
        return None
    return cleaned[:16]


def _dt(value) -> str | None:
    return value.isoformat() if value else None


def _temp_id() -> str:
    return uuid.uuid4().hex[:10]


def _color_for_index(i: int) -> str:
    return DEFAULT_COLORS[i % len(DEFAULT_COLORS)]


async def _notebook_count(session: AsyncSession, tag_id: int) -> int:
    stmt = (
        select(func.count())
        .select_from(NotebookTag)
        .join(Notebook, Notebook.id == NotebookTag.notebook_id)
        .where(
            NotebookTag.tag_id == tag_id,
            Notebook.deleted_at.is_(None),
        )
    )
    return int((await session.scalar(stmt)) or 0)


async def _to_read(session: AsyncSession, tag: Tag) -> dict:
    # Read columns before any await — expire_on_commit + async can otherwise
    # raise MissingGreenlet when accessing attrs after another DB await.
    tag_id = int(tag.id)
    name = tag.name
    color = tag.color
    created_at = tag.created_at
    updated_at = tag.updated_at
    return {
        "id": tag_id,
        "name": name,
        "color": color,
        "notebook_count": await _notebook_count(session, tag_id),
        "created_at": _dt(created_at),
        "updated_at": _dt(updated_at),
    }


async def get_owned_tag(session: AsyncSession, user_id: int, tag_id: int) -> Tag:
    tag = await session.get(Tag, tag_id)
    if tag is None or tag.owner_id != user_id:
        raise NotFoundError("标签不存在")
    return tag


async def list_tags(session: AsyncSession, user_id: int) -> list[dict]:
    rows = (
        await session.execute(
            select(Tag).where(Tag.owner_id == user_id).order_by(Tag.id.asc())
        )
    ).scalars().all()
    return [await _to_read(session, row) for row in rows]


async def create_tag(
    session: AsyncSession,
    user_id: int,
    *,
    name: str,
    color: str | None = None,
) -> dict:
    cleaned = _normalize_name(name)
    existing = (
        await session.execute(
            select(Tag).where(Tag.owner_id == user_id, Tag.name == cleaned)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise BadRequestError("标签已存在")
    count = (
        await session.scalar(select(func.count()).select_from(Tag).where(Tag.owner_id == user_id))
    ) or 0
    tag = Tag(
        owner_id=user_id,
        name=cleaned,
        color=_normalize_color(color) or _color_for_index(int(count)),
    )
    session.add(tag)
    await session.commit()
    await session.refresh(tag)
    return await _to_read(session, tag)


async def update_tag(
    session: AsyncSession,
    user_id: int,
    tag_id: int,
    *,
    name: str | None = None,
    color_provided: bool = False,
    color: str | None = None,
) -> dict:
    tag = await get_owned_tag(session, user_id, tag_id)
    if name is not None:
        cleaned = _normalize_name(name)
        clash = (
            await session.execute(
                select(Tag).where(
                    Tag.owner_id == user_id,
                    Tag.name == cleaned,
                    Tag.id != tag.id,
                )
            )
        ).scalar_one_or_none()
        if clash is not None:
            raise BadRequestError("标签已存在")
        tag.name = cleaned
    if color_provided:
        tag.color = _normalize_color(color)
    session.add(tag)
    await session.commit()
    await session.refresh(tag)
    return await _to_read(session, tag)


async def delete_tag(session: AsyncSession, user_id: int, tag_id: int) -> None:
    tag = await get_owned_tag(session, user_id, tag_id)
    await session.delete(tag)
    await session.commit()


async def tags_for_notebooks(
    session: AsyncSession, user_id: int, notebook_ids: list[int]
) -> dict[int, list[dict]]:
    """Batch load tag briefs for notebooks owned by user."""
    if not notebook_ids:
        return {}
    rows = (
        await session.execute(
            select(NotebookTag.notebook_id, Tag)
            .join(Tag, Tag.id == NotebookTag.tag_id)
            .where(
                Tag.owner_id == user_id,
                NotebookTag.notebook_id.in_(notebook_ids),
            )
            .order_by(Tag.id.asc())
        )
    ).all()
    out: dict[int, list[dict]] = {int(nid): [] for nid in notebook_ids}
    for notebook_id, tag in rows:
        out.setdefault(int(notebook_id), []).append(
            {"id": tag.id, "name": tag.name, "color": tag.color}
        )
    return out


async def get_notebook_tags(
    session: AsyncSession, user_id: int, notebook_id: int
) -> dict:
    await notebook_svc.get_notebook(session, owner_id=user_id, notebook_id=notebook_id)
    mapping = await tags_for_notebooks(session, user_id, [notebook_id])
    tags = mapping.get(notebook_id, [])
    return {"tag_ids": [t["id"] for t in tags], "tags": tags}


async def set_notebook_tags(
    session: AsyncSession,
    user_id: int,
    notebook_id: int,
    tag_ids: list[int],
) -> dict:
    await notebook_svc.get_notebook(session, owner_id=user_id, notebook_id=notebook_id)
    unique_ids = list(dict.fromkeys(tag_ids))
    if unique_ids:
        owned = (
            await session.execute(
                select(Tag.id).where(Tag.owner_id == user_id, Tag.id.in_(unique_ids))
            )
        ).scalars().all()
        if set(owned) != set(unique_ids):
            raise BadRequestError("标签无效")
    await session.execute(
        delete(NotebookTag).where(NotebookTag.notebook_id == notebook_id)
    )
    for tag_id in unique_ids:
        session.add(NotebookTag(tag_id=tag_id, notebook_id=notebook_id))
    await session.commit()
    return await get_notebook_tags(session, user_id, notebook_id)


_AUTO_ORG_SYSTEM = """你是笔记本标签助手。根据用户给出的笔记本「名称」和「描述」（没有正文），
为它们生成若干标签，并给每本笔记本分配一个或多个标签。

硬性要求：
1. 标签名称用简短中文（2–8 字），贴合主题，不要编号、不要「标签1」这类空名。
2. 每本笔记本至少 1 个标签，可以多个；不要遗漏笔记本。
3. 标签数量要合理：笔记本少时少几个，多时也不要超过 12 个标签。
4. 相近主题合并到同一标签；不要为每本单独造一个标签。
5. 只输出严格 JSON，不要 markdown 围栏，不要解释。

JSON 格式：
{"tags":[{"name":"标签名"}],"assignments":[{"notebook_id":1,"tag_names":["标签名"]}]}
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
) -> tuple[list[dict], list[dict]]:
    """Return (tags[{temp_id,name,color}], assignments[{notebook_id,tag_temp_ids}])."""
    owned_ids = [int(n["id"]) for n in notebooks]
    owned_set = set(owned_ids)

    tag_name_to_temp: dict[str, str] = {}
    tags_out: list[dict] = []

    def ensure_tag(name: str) -> str:
        cleaned = _normalize_name(str(name or "未命名"))
        if cleaned in tag_name_to_temp:
            return tag_name_to_temp[cleaned]
        tid = _temp_id()
        tag_name_to_temp[cleaned] = tid
        tags_out.append(
            {
                "temp_id": tid,
                "name": cleaned,
                "color": _color_for_index(len(tags_out)),
            }
        )
        return tid

    raw_tags = (raw or {}).get("tags") if isinstance(raw, dict) else None
    if isinstance(raw_tags, list):
        for item in raw_tags:
            if isinstance(item, dict):
                ensure_tag(str(item.get("name") or ""))
            elif isinstance(item, str):
                ensure_tag(item)

    assign_map: dict[int, list[str]] = {nid: [] for nid in owned_ids}
    raw_assignments = (raw or {}).get("assignments") if isinstance(raw, dict) else None
    if isinstance(raw_assignments, list):
        for item in raw_assignments:
            if not isinstance(item, dict):
                continue
            try:
                nid = int(item.get("notebook_id"))
            except (TypeError, ValueError):
                continue
            if nid not in owned_set:
                continue
            names = item.get("tag_names") or item.get("tags") or []
            temp_ids = item.get("tag_temp_ids") or []
            resolved: list[str] = []
            if isinstance(names, list):
                for n in names:
                    if isinstance(n, str) and n.strip():
                        resolved.append(ensure_tag(n))
            if isinstance(temp_ids, list) and not resolved:
                # map temp ids only if we already have them from tags list
                known = {t["temp_id"] for t in tags_out}
                for t in temp_ids:
                    if isinstance(t, str) and t in known and t not in resolved:
                        resolved.append(t)
            # also accept tag names as strings when LLM nests differently
            assign_map[nid] = list(dict.fromkeys(resolved))

    # legacy shape: tags with notebook_ids
    if isinstance(raw_tags, list):
        for item in raw_tags:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not name:
                continue
            tid = ensure_tag(str(name))
            ids_raw = item.get("notebook_ids") or item.get("notebookIds") or []
            if not isinstance(ids_raw, list):
                continue
            for x in ids_raw:
                try:
                    nid = int(x)
                except (TypeError, ValueError):
                    continue
                if nid in owned_set and tid not in assign_map[nid]:
                    assign_map[nid].append(tid)

    missing = [nid for nid, tids in assign_map.items() if not tids]
    if missing:
        tid = ensure_tag("未归类")
        for nid in missing:
            assign_map[nid].append(tid)

    if not tags_out and owned_ids:
        tid = ensure_tag("未归类")
        for nid in owned_ids:
            assign_map[nid] = [tid]

    assignments = [
        {"notebook_id": nid, "tag_temp_ids": assign_map.get(nid, [])}
        for nid in owned_ids
    ]
    # Drop tags that no notebook is assigned to (LLM may invent unused labels).
    used = {tid for a in assignments for tid in a["tag_temp_ids"]}
    tags_out = [t for t in tags_out if t["temp_id"] in used]
    return tags_out, assignments


async def preview_auto_organize(session: AsyncSession, user_id: int) -> dict:
    notebooks = await _list_user_notebook_briefs(session, user_id)
    if not notebooks:
        return {
            "tags": [],
            "assignments": [],
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
        "请根据下列笔记本的名称与描述生成标签与归属方案。\n\n"
        + json.dumps(payload, ensure_ascii=False)
    )

    message: str | None = None
    parsed: dict[str, Any] | None = None
    trace_id = None
    try:
        llm = await get_active_llm(session)
        provider = make_provider(
            provider_name=llm.provider,
            api_key=llm.api_key,
            base_url=llm.base_url,
            model_name=llm.model_name,
            params_json=llm.params_json,
        )
        trace_id = start_llm_trace(
            kind="tags",
            provider=llm.provider,
            model_name=llm.model_name,
        )
        llm_span(trace_id, "system", content=_AUTO_ORG_SYSTEM)
        llm_span(trace_id, "user", content=user_prompt)
        raw_text = await provider.complete(
            user_prompt,
            system=_AUTO_ORG_SYSTEM,
            max_tokens=4096,
            temperature=0.3,
        )
        llm_span(trace_id, "assistant", content=raw_text or "")
        parsed = _extract_json_obj(raw_text)
        if parsed is None:
            parsed = {
                "tags": [{"name": "未归类"}],
                "assignments": [
                    {"notebook_id": n["id"], "tag_names": ["未归类"]}
                    for n in notebooks
                ],
            }
            message = "模型返回无法解析，已给出兜底方案，请手工调整"
            end_llm_trace(trace_id, status="ok", error_text=message)
        else:
            end_llm_trace(trace_id, status="ok")
    except Exception as exc:  # noqa: BLE001
        if trace_id:
            end_llm_trace(trace_id, status="error", error_text=str(exc))
        parsed = {
            "tags": [{"name": "未归类"}],
            "assignments": [
                {"notebook_id": n["id"], "tag_names": ["未归类"]}
                for n in notebooks
            ],
        }
        message = f"分析失败（{exc}），已给出兜底方案，请手工调整"

    tags, assignments = _normalize_preview_plan(parsed, notebooks)
    return {
        "tags": tags,
        "assignments": assignments,
        "notebooks": notebooks,
        "message": message,
    }


async def apply_auto_organize(
    session: AsyncSession,
    user_id: int,
    tags_in: list[dict],
    assignments_in: list[dict],
) -> list[dict]:
    notebooks = await _list_user_notebook_briefs(session, user_id)
    owned_ids = {int(n["id"]) for n in notebooks}
    if not owned_ids:
        raise BadRequestError("没有可整理的笔记本")
    if not tags_in:
        raise BadRequestError("请至少保留一个标签")

    temp_to_name: dict[str, str] = {}
    temp_to_color: dict[str, str | None] = {}
    for i, item in enumerate(tags_in):
        tid = str(item.get("temp_id") or "").strip()
        if not tid:
            raise BadRequestError("标签缺少 temp_id")
        name = _normalize_name(str(item.get("name") or ""))
        if name in temp_to_name.values():
            raise BadRequestError(f"标签名称重复: {name}")
        temp_to_name[tid] = name
        temp_to_color[tid] = _normalize_color(item.get("color")) or _color_for_index(i)

    assign_map: dict[int, list[str]] = {}
    for item in assignments_in:
        try:
            nid = int(item.get("notebook_id"))
        except (TypeError, ValueError) as exc:
            raise BadRequestError("notebook_id 无效") from exc
        if nid not in owned_ids:
            raise BadRequestError(f"笔记本无效: {nid}")
        tids_raw = item.get("tag_temp_ids") or []
        if not isinstance(tids_raw, list):
            raise BadRequestError("tag_temp_ids 格式错误")
        tids: list[str] = []
        for t in tids_raw:
            ts = str(t)
            if ts not in temp_to_name:
                raise BadRequestError(f"未知标签: {ts}")
            if ts not in tids:
                tids.append(ts)
        assign_map[nid] = tids

    # notebooks not listed get empty tags (cover)
    for nid in owned_ids:
        assign_map.setdefault(nid, [])

    # Never create tags that no notebook will reference.
    used_temp_ids = {tid for tids in assign_map.values() for tid in tids}
    if not used_temp_ids:
        raise BadRequestError("请至少给一本笔记本关联一个标签")
    temp_to_name = {tid: name for tid, name in temp_to_name.items() if tid in used_temp_ids}
    temp_to_color = {tid: temp_to_color[tid] for tid in temp_to_name}

    try:
        # Tags currently linked to notebooks we are about to cover — after cover,
        # any of these with zero remaining links are auto-org orphans to delete
        # (manually created never-linked empty tags are not in this set).
        previously_linked = set(
            (
                await session.execute(
                    select(NotebookTag.tag_id).where(
                        NotebookTag.notebook_id.in_(list(owned_ids))
                    )
                )
            ).scalars().all()
        )
        previously_linked = {int(x) for x in previously_linked}

        # ensure tag entities only for used temp ids (create missing by name; reuse)
        existing_tags = (
            await session.execute(select(Tag).where(Tag.owner_id == user_id))
        ).scalars().all()
        by_name = {t.name: t for t in existing_tags}
        temp_to_db_id: dict[str, int] = {}
        for tid, name in temp_to_name.items():
            if name in by_name:
                tag = by_name[name]
                color = temp_to_color.get(tid)
                if color and tag.color != color:
                    tag.color = color
                    session.add(tag)
                temp_to_db_id[tid] = tag.id
            else:
                tag = Tag(
                    owner_id=user_id,
                    name=name,
                    color=temp_to_color.get(tid),
                )
                session.add(tag)
                await session.flush()
                by_name[name] = tag
                temp_to_db_id[tid] = tag.id

        # replace all notebook_tag rows for this user's notebooks
        await session.execute(
            delete(NotebookTag).where(NotebookTag.notebook_id.in_(list(owned_ids)))
        )
        for nid, tids in assign_map.items():
            for tid in tids:
                if tid not in temp_to_db_id:
                    continue
                session.add(
                    NotebookTag(tag_id=temp_to_db_id[tid], notebook_id=nid)
                )

        await session.flush()

        # Drop tags orphaned by this cover (had links before, zero links now).
        still_linked = set(
            (
                await session.execute(
                    select(NotebookTag.tag_id).where(
                        NotebookTag.tag_id.in_(list(previously_linked) or [0])
                    )
                )
            ).scalars().all()
        )
        still_linked = {int(x) for x in still_linked}
        orphan_ids = previously_linked - still_linked
        plan_db_ids = set(temp_to_db_id.values())
        orphan_ids -= plan_db_ids

        # Sweep any other zero-link tags for this owner (leftovers from older
        # applies already empty before this cover). Skip tags in the new plan.
        linked_any = set(
            (
                await session.execute(
                    select(NotebookTag.tag_id)
                    .join(Tag, Tag.id == NotebookTag.tag_id)
                    .where(Tag.owner_id == user_id)
                )
            ).scalars().all()
        )
        linked_any = {int(x) for x in linked_any}
        all_owner = (
            await session.execute(select(Tag.id).where(Tag.owner_id == user_id))
        ).scalars().all()
        empty_ids = {int(x) for x in all_owner} - linked_any - plan_db_ids
        to_delete = orphan_ids | empty_ids
        if to_delete:
            await session.execute(
                delete(Tag).where(Tag.owner_id == user_id, Tag.id.in_(list(to_delete)))
            )

        await session.commit()
    except Exception:
        await session.rollback()
        raise

    # return tags that were part of the plan (resolved entities)
    result: list[dict] = []
    plan_ids = list(temp_to_db_id.values())
    rows = (
        await session.execute(select(Tag).where(Tag.id.in_(plan_ids)).order_by(Tag.id.asc()))
    ).scalars().all()
    for tag in rows:
        result.append(await _to_read(session, tag))
    return result


async def migrate_collections_for_user(session: AsyncSession, user_id: int) -> int:
    """One-shot helper: copy collections -> tags for a user. Returns links created."""
    from app.models.collection import Collection, CollectionNotebook

    collections = (
        await session.execute(
            select(Collection).where(Collection.owner_id == user_id).order_by(Collection.id.asc())
        )
    ).scalars().all()
    if not collections:
        return 0
    existing = {
        t.name: t
        for t in (
            await session.execute(select(Tag).where(Tag.owner_id == user_id))
        ).scalars().all()
    }
    created_links = 0
    for i, coll in enumerate(collections):
        name = _normalize_name(coll.name)
        tag = existing.get(name)
        if tag is None:
            tag = Tag(
                owner_id=user_id,
                name=name,
                color=_color_for_index(i),
            )
            session.add(tag)
            await session.flush()
            existing[name] = tag
        member_ids = (
            await session.execute(
                select(CollectionNotebook.notebook_id).where(
                    CollectionNotebook.collection_id == coll.id
                )
            )
        ).scalars().all()
        for nid in member_ids:
            exists_link = (
                await session.execute(
                    select(NotebookTag).where(
                        NotebookTag.tag_id == tag.id,
                        NotebookTag.notebook_id == int(nid),
                    )
                )
            ).scalar_one_or_none()
            if exists_link is None:
                session.add(NotebookTag(tag_id=tag.id, notebook_id=int(nid)))
                created_links += 1
    await session.commit()
    return created_links
