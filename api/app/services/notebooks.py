"""Notebook CRUD 服务。

多租户隔离：所有查询过滤 owner_id；admin 也只能看自己的 notebook。
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, case, exists, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.cover_url import expand_cover_url, normalize_cover_url
from app.core.errors import NotFoundError
from app.models.notebook import Note, Notebook, NotebookSource, Video
from app.models.notebook_index import NotebookIndexState
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
    match_hint: str | None = None,
    index_status: str | None = None,
    indexed_at: str | None = None,
    index_error: str | None = None,
    tags: list[dict] | None = None,
) -> dict:
    return {
        "id": nb.id,
        "title": nb.title,
        "description": nb.description,
        "icon": nb.icon,
        "cover_url": expand_cover_url(nb.cover_url),
        "is_pinned": nb.is_pinned,
        "share_all": nb.share_all,
        "owner_id": nb.owner_id,
        "owner_name": owner_name,
        "is_owner": (viewer_id == nb.owner_id) if viewer_id is not None else None,
        "source_count": source_count,
        "note_count": note_count,
        "match_hint": match_hint,
        "index_status": index_status,
        "indexed_at": indexed_at,
        "index_error": index_error,
        "tags": tags or [],
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



async def index_states_for_notebooks(
    session: AsyncSession, notebook_ids: list[int]
) -> dict[int, NotebookIndexState]:
    if not notebook_ids:
        return {}
    rows = (
        await session.execute(
            select(NotebookIndexState).where(
                NotebookIndexState.notebook_id.in_(notebook_ids)
            )
        )
    ).scalars().all()
    return {int(r.notebook_id): r for r in rows}


def _index_fields(
    state: NotebookIndexState | None, *, is_owner: bool
) -> dict[str, str | None]:
    if not is_owner:
        return {"index_status": None, "indexed_at": None, "index_error": None}
    if state is None:
        return {"index_status": "pending", "indexed_at": None, "index_error": None}
    return {
        "index_status": state.status,
        "indexed_at": state.indexed_at.isoformat() if state.indexed_at else None,
        "index_error": state.index_error,
    }

async def _owner_names(session: AsyncSession, owner_ids: list[int]) -> dict[int, str]:
    ids = sorted({int(i) for i in owner_ids if i is not None})
    if not ids:
        return {}
    rows = (
        await session.execute(select(User.id, User.name).where(User.id.in_(ids)))
    ).all()
    return {int(uid): name for uid, name in rows}



async def _tags_map(session: AsyncSession, notebook_ids: list[int], owner_id: int | None) -> dict[int, list[dict]]:
    if not notebook_ids or owner_id is None:
        return {}
    from app.services import tags as tags_svc
    return await tags_svc.tags_for_notebooks(session, owner_id, notebook_ids)

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
    states = await index_states_for_notebooks(session, [nb.id])
    is_owner = viewer_id == nb.owner_id if viewer_id is not None else False
    idx = _index_fields(states.get(nb.id), is_owner=is_owner)
    tag_owner = nb.owner_id if (viewer_id is None or viewer_id == nb.owner_id) else None
    tags_map = await _tags_map(session, [nb.id], tag_owner)
    return _to_read_dict(
        nb,
        source_count=source_count,
        note_count=note_count,
        owner_name=owner_name,
        viewer_id=viewer_id,
        tags=tags_map.get(nb.id, []),
        **idx,
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
    states = await index_states_for_notebooks(session, [nb.id for nb in notebooks])
    # Only expose tags for notebooks the viewer owns (or when no viewer).
    owned_ids = [
        nb.id
        for nb in notebooks
        if viewer_id is None or viewer_id == nb.owner_id
    ]
    tag_owner = None
    if notebooks:
        if viewer_id is not None:
            tag_owner = viewer_id
        else:
            tag_owner = notebooks[0].owner_id
    tags_map = await _tags_map(session, owned_ids, tag_owner)
    out: list[dict] = []
    for nb in notebooks:
        source_count, note_count = counts.get(nb.id, (0, 0))
        is_owner = viewer_id == nb.owner_id if viewer_id is not None else False
        idx = _index_fields(states.get(nb.id), is_owner=is_owner)
        out.append(
            _to_read_dict(
                nb,
                source_count=source_count,
                note_count=note_count,
                owner_name=names.get(nb.owner_id),
                viewer_id=viewer_id,
                tags=tags_map.get(nb.id, []) if is_owner or viewer_id is None else [],
                **idx,
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
    tag_id: int | None = None,
) -> tuple[list[Notebook], int]:
    stmt = select(Notebook).where(Notebook.owner_id == owner_id, Notebook.deleted_at.is_(None))
    if search:
        like = f"%{search}%"
        stmt = stmt.where(Notebook.title.like(like))
    if tag_id is not None:
        from app.models.tag import NotebookTag, Tag
        stmt = (
            stmt.join(NotebookTag, NotebookTag.notebook_id == Notebook.id)
            .join(Tag, Tag.id == NotebookTag.tag_id)
            .where(Tag.owner_id == owner_id, Tag.id == tag_id)
        )
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



def _like_term(q: str) -> str:
    """去掉通配符，避免用户输入 %/_ 扩大匹配面。"""
    return q.strip().replace("%", "").replace("_", "")


def _discover_scope_clause(viewer_id: int, scope: str):
    base = Notebook.deleted_at.is_(None)
    if scope == "mine":
        return and_(base, Notebook.owner_id == viewer_id)
    if scope == "shared":
        return and_(
            base,
            Notebook.share_all.is_(True),
            Notebook.owner_id != viewer_id,
        )
    # all：自己的全部 + 他人公开
    return and_(
        base,
        or_(
            Notebook.owner_id == viewer_id,
            and_(Notebook.share_all.is_(True), Notebook.owner_id != viewer_id),
        ),
    )




def _has_sources_clause():
    """笔记本至少有 1 个来源。"""
    return exists(
        select(literal(1))
        .select_from(NotebookSource)
        .where(NotebookSource.notebook_id == Notebook.id)
    )


async def _discover_candidate_ids(
    session: AsyncSession,
    *,
    viewer_id: int,
    scope: str,
    require_sources: bool = False,
) -> list[int]:
    clause = _discover_scope_clause(viewer_id, scope)
    if require_sources:
        clause = and_(clause, _has_sources_clause())
    rows = (
        await session.execute(select(Notebook.id).where(clause).order_by(Notebook.id.desc()))
    ).scalars().all()
    return [int(i) for i in rows]


# Cosine 相似度默认阈值（用户可在发现页搜索条件里改；空壳标题噪声多在 0.4~0.55）
SEMANTIC_MIN_SCORE_DEFAULT = 0.55
SEMANTIC_MIN_SCORE = SEMANTIC_MIN_SCORE_DEFAULT  # compat alias
SEMANTIC_MIN_SCORE_FLOOR = 0.0
SEMANTIC_MIN_SCORE_CEIL = 1.0


def clamp_semantic_min_score(value: float | None) -> float:
    """Clamp user/query min similarity to [0, 1]; default when missing/invalid."""
    if value is None:
        return SEMANTIC_MIN_SCORE_DEFAULT
    try:
        score = float(value)
    except (TypeError, ValueError):
        return SEMANTIC_MIN_SCORE_DEFAULT
    if score != score:  # NaN
        return SEMANTIC_MIN_SCORE_DEFAULT
    return max(SEMANTIC_MIN_SCORE_FLOOR, min(SEMANTIC_MIN_SCORE_CEIL, score))


def _semantic_match_hint(score: float) -> str:
    # Qdrant Cosine 返回的是相似度（约 0~1），不是距离；展示为百分比诚实映射
    pct = max(0, min(100, int(round(float(score) * 100))))
    if pct > 0:
        return f"语义相近 · {pct}%"
    return "语义相近"


async def _discover_semantic(
    session: AsyncSession,
    *,
    viewer_id: int,
    q: str,
    scope: str,
    page: int,
    size: int,
    min_score: float | None = None,
) -> tuple[list[tuple[Notebook, str | None]], int]:
    """语义检索：先按 scope 拿候选 id → embedding → Qdrant → 回表加载。"""
    threshold = clamp_semantic_min_score(min_score)
    from app.core.errors import NotFoundError, ServiceUnavailableError
    from app.llm.config_service import get_active_embedding
    from app.services.vector_settings import get_vector_settings_row
    from app.vector.embeddings import EmbeddingError, embed_query
    from app.vector.store import VectorStoreError, make_vector_store

    # 有查询时排除 0 来源空壳，避免标题噪声假阳性
    candidate_ids = await _discover_candidate_ids(
        session, viewer_id=viewer_id, scope=scope, require_sources=True
    )
    if not candidate_ids:
        return [], 0

    try:
        resolved = await get_active_embedding(session)
    except NotFoundError as exc:
        raise ServiceUnavailableError(
            "尚未配置向量模型。请到后台「默认模型」选择 Embedding，并确保凭证可用。"
        ) from exc

    try:
        query_vec = await embed_query(resolved, q)
    except EmbeddingError as exc:
        raise ServiceUnavailableError(
            f"向量化查询失败：{exc}。请检查向量模型与 API Key。"
        ) from exc

    settings = await get_vector_settings_row(session)
    try:
        store = make_vector_store(
            backend=settings.vector_backend or "qdrant",
            qdrant_url=settings.qdrant_url or "http://127.0.0.1:6333",
            qdrant_collection=settings.qdrant_collection or "notebooks",
            qdrant_api_key=settings.qdrant_api_key,
        )
        # 多取一些再本地按阈值过滤；上限保护大库
        fetch_limit = min(len(candidate_ids), max(page * size * 3, size * 3, 50), 500)
        hits = await store.search(
            query_vec,
            limit=fetch_limit,
            notebook_ids=candidate_ids,
            score_threshold=threshold,
        )
    except VectorStoreError as exc:
        raise ServiceUnavailableError(
            f"向量库不可用：{exc}。请确认 Qdrant 已启动，并在后台「向量配置」填写正确地址。"
        ) from exc

    # 只保留仍在候选集内、且达到最低相似度的命中
    allowed = set(candidate_ids)
    ordered: list[tuple[int, float]] = []
    seen: set[int] = set()
    for hit in hits:
        score = float(hit.score)
        if hit.notebook_id not in allowed or hit.notebook_id in seen:
            continue
        if score < threshold:
            continue
        seen.add(hit.notebook_id)
        ordered.append((hit.notebook_id, score))

    total = len(ordered)
    start = (page - 1) * size
    page_rows = ordered[start : start + size]
    if not page_rows:
        return [], total

    page_ids = [nid for nid, _ in page_rows]
    nb_rows = (
        await session.execute(select(Notebook).where(Notebook.id.in_(page_ids)))
    ).scalars().all()
    by_id = {nb.id: nb for nb in nb_rows}
    score_by_id = {nid: score for nid, score in page_rows}
    pairs: list[tuple[Notebook, str | None]] = []
    for nid in page_ids:
        nb = by_id.get(nid)
        if nb is None or nb.deleted_at is not None:
            continue
        # 再次校验 scope（防脏数据 / 索引滞后）
        if scope == "mine" and nb.owner_id != viewer_id:
            continue
        if scope == "shared" and (
            not nb.share_all or nb.owner_id == viewer_id
        ):
            continue
        if scope == "all" and nb.owner_id != viewer_id and not nb.share_all:
            continue
        pairs.append((nb, _semantic_match_hint(score_by_id.get(nid, 0.0))))
    return pairs, total

async def discover_notebooks(
    session: AsyncSession,
    *,
    viewer_id: int,
    q: str | None,
    scope: str,
    page: int,
    size: int,
    mode: str = "keyword",
    min_score: float | None = None,
) -> tuple[list[tuple[Notebook, str | None]], int]:
    """发现页浏览 / 关键词 / 语义搜索。

    scope=mine|shared|all；mode=keyword|semantic。
    空 q 按范围浏览（不走向量）；有 q 时 keyword 做 LIKE 加权，semantic 走 embedding+Qdrant。
    min_score 仅语义模式生效（0~1，默认 0.55）。
    绝不返回他人未公开的本。
    """
    if scope not in {"all", "mine", "shared"}:
        scope = "all"
    if mode not in {"keyword", "semantic"}:
        mode = "keyword"
    term = _like_term(q or "")
    if mode == "semantic" and term:
        return await _discover_semantic(
            session,
            viewer_id=viewer_id,
            q=term,
            scope=scope,
            page=page,
            size=size,
            min_score=min_score,
        )

    clause = _discover_scope_clause(viewer_id, scope)
    like = f"%{term}%" if term else None

    if like:
        # 有查询词时排除 0 来源空壳
        clause = and_(clause, _has_sources_clause())
        title_hit = Notebook.title.like(like)
        desc_hit = and_(
            Notebook.description.is_not(None),
            Notebook.description.like(like),
        )
        overview_hit = exists(
            select(literal(1))
            .select_from(NotebookSource)
            .join(Video, Video.id == NotebookSource.video_id)
            .where(
                NotebookSource.notebook_id == Notebook.id,
                Video.owner_id == Notebook.owner_id,
                Video.overview_text.is_not(None),
                Video.overview_text.like(like),
            )
        )
        score_expr = (
            case((title_hit, 100), else_=0)
            + case((desc_hit, 40), else_=0)
            + case((overview_hit, 20), else_=0)
        )
        hint_expr = case(
            (title_hit, literal("命中标题")),
            (desc_hit, literal("命中描述")),
            (overview_hit, literal("命中概览")),
            else_=None,
        )
        filtered = select(Notebook.id).where(
            clause,
            or_(title_hit, desc_hit, overview_hit),
        )
        total = (
            await session.scalar(select(func.count()).select_from(filtered.subquery()))
        ) or 0
        stmt = (
            select(Notebook, hint_expr.label("match_hint"), score_expr.label("score"))
            .where(clause, or_(title_hit, desc_hit, overview_hit))
            .order_by(score_expr.desc(), Notebook.updated_at.desc(), Notebook.id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        rows = (await session.execute(stmt)).all()
        return [(row[0], row[1]) for row in rows], int(total)

    # 空关键词：按范围浏览
    stmt = select(Notebook).where(clause)
    total = (
        await session.scalar(select(func.count()).select_from(stmt.subquery()))
    ) or 0
    if scope == "mine":
        stmt = stmt.order_by(Notebook.is_pinned.desc(), Notebook.id.desc())
    else:
        stmt = stmt.order_by(Notebook.updated_at.desc(), Notebook.id.desc())
    stmt = stmt.offset((page - 1) * size).limit(size)
    items = (await session.execute(stmt)).scalars().all()
    return [(nb, None) for nb in items], int(total)


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
        cover_url=normalize_cover_url(cover_url),
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
        nb.cover_url = normalize_cover_url(cover_url)
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
    now = datetime.now(UTC).replace(tzinfo=None)
    nb.deleted_at = now
    session.add(nb)
    # Soft-delete notes so admin content stats / lists stay consistent
    notes = (
        await session.execute(
            select(Note).where(
                Note.notebook_id == notebook_id,
                Note.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    for note in notes:
        note.deleted_at = now
        note.message_id = None
        session.add(note)
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
