"""本内知识底稿：生成、读取、更新勾选/结论。"""
from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, NotFoundError
from app.draft_strategy.defaults import (
    DEFAULT_PREFIX,
    OUTPUT_SCHEMA_INSTRUCTION,
)
from app.llm.config_service import get_active_llm
from app.llm.providers import make_provider
from app.models.draft_strategy import DraftStrategy
from app.models.knowledge_draft import NotebookKnowledgeDraft
from app.models.notebook import Note, NotebookSource, Video
from app.schemas.knowledge_draft import (
    DraftStrategyOption,
    KnowledgeDraftContent,
    KnowledgeDraftGenerateRequest,
    KnowledgeDraftRead,
    KnowledgeDraftUpdateRequest,
    KnowledgeDraftPointAskRequest,
    KnowledgeDraftPointAskResponse,
)
from app.services import notebooks as notebooks_svc
from app.services.draft_strategy import (
    _ensure_settings,
    _extract_json,
    _load_video_transcript,
    seed_builtin_strategies,
)

_MAX_COMBINED_CHARS = 28_000
def _new_id() -> str:
    return uuid.uuid4().hex[:12]


_EXAMPLE_KINDS = frozenset({"life", "allusion", "work", "other"})


def _normalize_conclusions(
    *,
    content: dict[str, Any] | None = None,
    conclusion_text: str | None = None,
    explicit: list[str] | None = None,
) -> list[str]:
    """应用层兼容：优先显式列表 → content_json.conclusions → 旧 conclusion 文本。"""
    if explicit is not None:
        return [s.strip() for s in explicit if isinstance(s, str) and s.strip()]

    content = content or {}
    raw = content.get("conclusions")
    if isinstance(raw, list):
        out = [str(x).strip() for x in raw if str(x or "").strip()]
        if out:
            return out

    text_v = (conclusion_text or "").strip()
    if not text_v:
        return []
    # 旧数据可能是单段；若含换行则按行拆（多条结论的简易存储）
    if "\n" in text_v:
        parts = [p.strip() for p in text_v.splitlines() if p.strip()]
        if parts:
            return parts
    return [text_v]


def _pack_conclusion_text(conclusions: list[str]) -> str:
    return "\n".join(c for c in conclusions if c.strip())

def _normalize_content(raw: dict[str, Any] | None, *, preserve_checks: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = raw or {}
    prev_points = {
        str(p.get("id")): p
        for p in (preserve_checks or {}).get("points") or []
        if isinstance(p, dict) and p.get("id")
    }
    prev_takes = {
        str(t.get("id")): t
        for t in (preserve_checks or {}).get("takeaways") or []
        if isinstance(t, dict) and t.get("id")
    }

    concepts: list[dict[str, str]] = []
    for item in raw.get("concepts") or []:
        if not isinstance(item, dict):
            continue
        term = str(item.get("term") or "").strip()
        definition = str(item.get("definition") or "").strip()
        if term or definition:
            concepts.append({"term": term or "概念", "definition": definition})

    points: list[dict[str, Any]] = []
    for item in raw.get("points") or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        pid = str(item.get("id") or "").strip() or _new_id()
        time_v = item.get("time")
        time_s = str(time_v).strip() if time_v else None
        if time_s == "":
            time_s = None
        evidence = item.get("evidence")
        evidence_s = str(evidence).strip() if evidence else None
        hint = item.get("source_hint")
        hint_s = str(hint).strip() if hint else None
        video_id = item.get("video_id")
        try:
            video_id_i = int(video_id) if video_id is not None else None
        except (TypeError, ValueError):
            video_id_i = None
        checked = bool(item.get("checked", False))
        if pid in prev_points:
            checked = bool(prev_points[pid].get("checked", checked))
        example = item.get("example")
        example_s = str(example).strip() if example else None
        if example_s == "":
            example_s = None
        kind_raw = str(item.get("example_kind") or "").strip().lower() or None
        example_kind = kind_raw if kind_raw in _EXAMPLE_KINDS else None
        comment = item.get("comment")
        comment_s = str(comment).strip() if comment else None
        if comment_s == "":
            comment_s = None
        if pid in prev_points and comment_s is None:
            prev_c = prev_points[pid].get("comment")
            prev_cs = str(prev_c).strip() if prev_c else None
            comment_s = prev_cs or None
        points.append(
            {
                "id": pid,
                "text": text,
                "time": time_s,
                "evidence": evidence_s or None,
                "source_hint": hint_s or None,
                "video_id": video_id_i,
                "checked": checked,
                "example": example_s,
                "example_kind": example_kind,
                "comment": comment_s,
            }
        )

    takeaways: list[dict[str, Any]] = []
    for item in raw.get("takeaways") or []:
        if isinstance(item, str):
            text = item.strip()
            if not text:
                continue
            takeaways.append({"id": _new_id(), "text": text, "checked": False})
            continue
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        tid = str(item.get("id") or "").strip() or _new_id()
        checked = bool(item.get("checked", False))
        if tid in prev_takes:
            checked = bool(prev_takes[tid].get("checked", checked))
        takeaways.append({"id": tid, "text": text, "checked": checked})

    open_questions: list[str] = []
    for item in raw.get("open_questions") or []:
        if isinstance(item, str) and item.strip():
            open_questions.append(item.strip())

    theme = str(raw.get("theme") or "").strip()
    conclusions = _normalize_conclusions(content=raw)
    out: dict[str, Any] = {
        "theme": theme,
        "concepts": concepts,
        "points": points,
        "takeaways": takeaways,
        "open_questions": open_questions,
    }
    if conclusions:
        out["conclusions"] = conclusions
    return out


def _to_read(row: NotebookKnowledgeDraft, strategy_title: str | None = None) -> KnowledgeDraftRead:
    raw = row.content_json if isinstance(row.content_json, dict) else {}
    content = _normalize_content(raw)
    conclusions = _normalize_conclusions(
        content=content if isinstance(content, dict) else {},
        conclusion_text=row.conclusion or "",
    )
    # KnowledgeDraftContent 不含 conclusions；从 content 副本剥离再校验
    content_for_model = {k: v for k, v in content.items() if k != "conclusions"}
    return KnowledgeDraftRead(
        id=int(row.id),
        notebook_id=int(row.notebook_id),
        strategy_id=int(row.strategy_id) if row.strategy_id is not None else None,
        strategy_title=strategy_title,
        status=row.status,
        language=row.language or "中文",
        model_ref=row.model_ref or "inherit",
        model_used=row.model_used,
        conclusion=_pack_conclusion_text(conclusions),
        conclusions=conclusions,
        content=KnowledgeDraftContent.model_validate(content_for_model),
        source_video_ids=list(row.source_video_ids or []),
        source_note_ids=list(row.source_note_ids or []),
        focus=row.focus,
        extra_constraints=row.extra_constraints,
        error_message=row.error_message,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def list_enabled_strategies(session: AsyncSession) -> list[DraftStrategyOption]:
    await seed_builtin_strategies(session)
    rows = (
        await session.execute(
            select(DraftStrategy)
            .where(DraftStrategy.enabled.is_(True))
            .order_by(DraftStrategy.is_builtin.desc(), DraftStrategy.id.asc())
        )
    ).scalars().all()
    return [
        DraftStrategyOption(
            id=int(r.id),
            name=r.name,
            title=r.title,
            description=r.description or "",
            kind=r.kind,
            apply_default=bool(r.apply_default),
            suggested_model=r.suggested_model,  # type: ignore[arg-type]
            min_sources=int(r.min_sources),
        )
        for r in rows
    ]


async def get_draft(
    session: AsyncSession, *, owner_id: int, notebook_id: int
) -> KnowledgeDraftRead | None:
    await notebooks_svc.get_notebook(session, owner_id=owner_id, notebook_id=notebook_id)
    row = (
        await session.execute(
            select(NotebookKnowledgeDraft).where(
                NotebookKnowledgeDraft.notebook_id == notebook_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    title = None
    if row.strategy_id is not None:
        strat = await session.get(DraftStrategy, row.strategy_id)
        title = strat.title if strat else None
    return _to_read(row, strategy_title=title)


async def _load_note_text(session: AsyncSession, note_id: int) -> str:
    note = await session.get(Note, note_id)
    if note is None or note.deleted_at is not None:
        raise NotFoundError(f"笔记 {note_id} 不存在")
    body = (note.content_text or "").strip()
    if not body:
        raise BadRequestError(f"笔记「{note.title}」内容为空")
    return f"笔记标题：{note.title}\n\n正文：\n{body}"


async def _validate_sources(
    session: AsyncSession,
    *,
    notebook_id: int,
    video_ids: list[int],
    note_ids: list[int],
) -> None:
    if not video_ids and not note_ids:
        raise BadRequestError("请至少选择一个来源")

    if video_ids:
        linked = (
            await session.execute(
                select(NotebookSource.video_id).where(
                    NotebookSource.notebook_id == notebook_id,
                    NotebookSource.video_id.in_(video_ids),
                )
            )
        ).scalars().all()
        if set(linked) != set(video_ids):
            raise BadRequestError("部分视频不在本笔记本中")

    if note_ids:
        found = (
            await session.execute(
                select(Note.id).where(
                    Note.notebook_id == notebook_id,
                    Note.id.in_(note_ids),
                    Note.deleted_at.is_(None),
                )
            )
        ).scalars().all()
        if set(found) != set(note_ids):
            raise BadRequestError("部分笔记不在本笔记本中")


async def _build_source_material(
    session: AsyncSession,
    *,
    video_ids: list[int],
    note_ids: list[int],
) -> str:
    chunks: list[str] = []
    total = 0
    for vid in video_ids:
        video = await session.get(Video, vid)
        label = (video.title if video else None) or f"视频 {vid}"
        try:
            text = await _load_video_transcript(session, vid)
        except BadRequestError:
            raise
        except NotFoundError:
            raise
        block = f"### 来源 video:{vid}（{label}）\n{text}"
        if total + len(block) > _MAX_COMBINED_CHARS:
            remain = max(0, _MAX_COMBINED_CHARS - total - 80)
            block = block[:remain] + "\n…(截断)"
            chunks.append(block)
            break
        chunks.append(block)
        total += len(block)

    for nid in note_ids:
        if total >= _MAX_COMBINED_CHARS:
            break
        note = await session.get(Note, nid)
        label = (note.title if note else None) or f"笔记 {nid}"
        text = await _load_note_text(session, nid)
        block = f"### 来源 note:{nid}（{label}）\n{text}"
        if total + len(block) > _MAX_COMBINED_CHARS:
            remain = max(0, _MAX_COMBINED_CHARS - total - 80)
            block = block[:remain] + "\n…(截断)"
            chunks.append(block)
            break
        chunks.append(block)
        total += len(block)

    if not chunks:
        raise BadRequestError("没有可用的来源文本（需字幕就绪或非空笔记）")
    return "\n\n".join(chunks)


async def generate_draft(
    session: AsyncSession,
    *,
    owner_id: int,
    notebook_id: int,
    body: KnowledgeDraftGenerateRequest,
) -> KnowledgeDraftRead:
    await notebooks_svc.get_notebook(session, owner_id=owner_id, notebook_id=notebook_id)
    await seed_builtin_strategies(session)

    strategy = await session.get(DraftStrategy, body.strategy_id)
    if strategy is None or not strategy.enabled:
        raise NotFoundError("策略不存在或已停用")

    video_ids = list(dict.fromkeys(int(i) for i in body.video_ids))
    note_ids = list(dict.fromkeys(int(i) for i in body.note_ids))
    source_count = len(video_ids) + len(note_ids)
    if source_count < int(strategy.min_sources):
        raise BadRequestError(
            f"策略「{strategy.title}」至少需要 {strategy.min_sources} 个来源"
        )

    await _validate_sources(
        session, notebook_id=notebook_id, video_ids=video_ids, note_ids=note_ids
    )
    material = await _build_source_material(
        session, video_ids=video_ids, note_ids=note_ids
    )

    settings = await _ensure_settings(session)
    prefix = (settings.default_prefix or DEFAULT_PREFIX).strip()
    strategy_prompt = (strategy.prompt or "").strip()

    resolved_ref = body.model or strategy.suggested_model or "inherit"
    if resolved_ref == "inherit":
        resolved_ref = settings.default_model_ref or "chat"

    # 本内生成走聊天模型；Claude Code 面向 Studio 工作区
    model_note = None
    if resolved_ref == "claude_code":
        model_note = "已改用默认聊天模型生成底稿（Claude Code 仅用于 Studio）"
        resolved_ref = "chat"

    llm = await get_active_llm(session)
    provider = make_provider(
        provider_name=llm.provider,
        api_key=llm.api_key,
        base_url=llm.base_url,
        model_name=llm.model_name,
        params_json=llm.params_json,
    )

    lang_line = f"输出语言：{body.language}"
    extra_bits = [lang_line]
    if body.focus and body.focus.strip():
        extra_bits.append(f"用户聚焦：{body.focus.strip()}")
    if body.extra_constraints and body.extra_constraints.strip():
        extra_bits.append(f"额外约束：{body.extra_constraints.strip()}")
    extra_bits.append(
        f"来源列表：videos={video_ids} notes={note_ids}；"
        "points 里如能判断来源，可写 source_hint（如 video:12）或 video_id 数字。"
    )

    system = "\n\n".join(p for p in [prefix, OUTPUT_SCHEMA_INSTRUCTION] if p)
    user_prompt = (
        f"{strategy_prompt}\n\n"
        + "\n".join(extra_bits)
        + f"\n\n---\n来源材料：\n{material}"
    )

    try:
        raw_text = await provider.complete(
            user_prompt,
            system=system,
            max_tokens=4000,
        )
    except Exception as exc:  # noqa: BLE001
        raise BadRequestError(f"模型调用失败：{exc}") from exc

    preview, parse_error = _extract_json(raw_text or "")
    if preview is None:
        raise BadRequestError(parse_error or "无法解析模型输出为底稿 JSON")

    content = _normalize_content(preview)
    missing_ex = [p for p in content["points"] if not (p.get("example") or "").strip()]
    if missing_ex and content["points"]:
        try:
            by_id: dict[str, tuple[str, str | None]] = {}
            for i in range(0, len(missing_ex), 8):
                chunk = missing_ex[i : i + 8]
                payload = [{"id": p["id"], "text": p["text"]} for p in chunk]
                repair_prompt = (
                    "为下列知识要点各写一个短例子（生活场景或典故，1-2句），帮助理解。\n"
                    + '只输出 JSON：{"examples":[{"id":"...","example":"...","example_kind":"life|allusion|work|other"}]}\n'
                    + "硬性：每条 id 对应一条非空 example；不要抄字幕原句；不要 Markdown。\n"
                    + f"要点JSON：{json.dumps(payload, ensure_ascii=False)}"
                )
                repair_raw = await provider.complete(
                    repair_prompt,
                    system="只输出 JSON 对象。",
                    max_tokens=2500,
                )
                repair_obj, _ = _extract_json(repair_raw or "")
                if not isinstance(repair_obj, dict):
                    continue
                for row_ex in repair_obj.get("examples") or []:
                    if not isinstance(row_ex, dict):
                        continue
                    pid = str(row_ex.get("id") or "").strip()
                    ex = str(row_ex.get("example") or "").strip()
                    if not pid or not ex:
                        continue
                    kind = str(row_ex.get("example_kind") or "").strip().lower() or None
                    by_id[pid] = (ex, kind if kind in _EXAMPLE_KINDS else None)
            for p in content["points"]:
                if (p.get("example") or "").strip():
                    continue
                hit = by_id.get(p["id"])
                if hit:
                    p["example"], p["example_kind"] = hit
        except Exception:
            pass
    # 若只有一个视频来源，把未标 video_id 的要点默认挂上
    if len(video_ids) == 1:
        only = video_ids[0]
        for p in content["points"]:
            if p.get("video_id") is None:
                p["video_id"] = only

    existing = (
        await session.execute(
            select(NotebookKnowledgeDraft).where(
                NotebookKnowledgeDraft.notebook_id == notebook_id
            )
        )
    ).scalar_one_or_none()

    # 重新生成时保留要点评论（先 id，再 text）
    if existing is not None:
        prev_raw = existing.content_json if isinstance(existing.content_json, dict) else {}
        prev_pts = [
            p for p in (prev_raw.get("points") or []) if isinstance(p, dict) and p.get("id")
        ]
        by_id = {
            str(p["id"]): (str(p.get("comment") or "").strip() or None) for p in prev_pts
        }
        by_text: dict[str, str] = {}
        for p in prev_pts:
            c = str(p.get("comment") or "").strip()
            tx = str(p.get("text") or "").strip()
            if c and tx and tx not in by_text:
                by_text[tx] = c
        for p in content["points"]:
            if (p.get("comment") or "").strip():
                continue
            hit = by_id.get(str(p["id"]))
            if not hit:
                hit = by_text.get(str(p.get("text") or "").strip())
            if hit:
                p["comment"] = hit

    # 重新生成时保留用户结论（多条）

    keep_conclusions: list[str] = []
    if existing is not None:
        prev = existing.content_json if isinstance(existing.content_json, dict) else {}
        keep_conclusions = _normalize_conclusions(
            content=prev, conclusion_text=existing.conclusion or ""
        )
    if keep_conclusions:
        content = {**content, "conclusions": keep_conclusions}
    keep_conclusion = _pack_conclusion_text(keep_conclusions)

    if existing is None:
        row = NotebookKnowledgeDraft(
            notebook_id=notebook_id,
            owner_id=owner_id,
            strategy_id=int(strategy.id),
            status="ready",
            language=body.language,
            model_ref=body.model,
            model_used=f"{llm.provider}:{llm.model_name}"
            + (f"（{model_note}）" if model_note else ""),
            conclusion=keep_conclusion,
            content_json=content,
            source_video_ids=video_ids,
            source_note_ids=note_ids,
            focus=(body.focus or "").strip() or None,
            extra_constraints=(body.extra_constraints or "").strip() or None,
            error_message=None,
        )
        session.add(row)
    else:
        existing.strategy_id = int(strategy.id)
        existing.status = "ready"
        existing.language = body.language
        existing.model_ref = body.model
        existing.model_used = f"{llm.provider}:{llm.model_name}" + (
            f"（{model_note}）" if model_note else ""
        )
        existing.content_json = content
        existing.conclusion = keep_conclusion
        existing.source_video_ids = video_ids
        existing.source_note_ids = note_ids
        existing.focus = (body.focus or "").strip() or None
        existing.extra_constraints = (body.extra_constraints or "").strip() or None
        existing.error_message = None
        session.add(existing)
        row = existing

    await session.commit()
    await session.refresh(row)
    return _to_read(row, strategy_title=strategy.title)


async def update_draft(
    session: AsyncSession,
    *,
    owner_id: int,
    notebook_id: int,
    body: KnowledgeDraftUpdateRequest,
) -> KnowledgeDraftRead:
    await notebooks_svc.get_notebook(session, owner_id=owner_id, notebook_id=notebook_id)
    row = (
        await session.execute(
            select(NotebookKnowledgeDraft).where(
                NotebookKnowledgeDraft.notebook_id == notebook_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("尚未生成知识底稿")

    raw_content = row.content_json if isinstance(row.content_json, dict) else {}
    content = _normalize_content(raw_content)

    if body.conclusions is not None:
        conclusions = list(body.conclusions)
        content["conclusions"] = conclusions
        row.conclusion = _pack_conclusion_text(conclusions)
    elif body.conclusion is not None:
        # 旧单字段：拆成多条（按行）或单条
        conclusions = _normalize_conclusions(conclusion_text=body.conclusion)
        content["conclusions"] = conclusions
        row.conclusion = _pack_conclusion_text(conclusions)

    if body.checked_point_ids is not None:
        wanted = set(body.checked_point_ids)
        for p in content["points"]:
            p["checked"] = p["id"] in wanted

    if body.checked_takeaway_ids is not None:
        wanted = set(body.checked_takeaway_ids)
        for t in content["takeaways"]:
            t["checked"] = t["id"] in wanted

    if body.point_text_updates:
        for pid, text in body.point_text_updates.items():
            for p in content["points"]:
                if p["id"] == pid:
                    new_text = (text or "").strip()
                    if new_text:
                        p["text"] = new_text
                    break

    if body.point_comment_updates is not None:
        for pid, comment in body.point_comment_updates.items():
            for p in content["points"]:
                if p["id"] == pid:
                    if comment is None:
                        p["comment"] = None
                    else:
                        s = str(comment).strip()
                        p["comment"] = s[:4000] if s else None
                    break

    row.content_json = content
    session.add(row)
    await session.commit()
    await session.refresh(row)

    title = None
    if row.strategy_id is not None:
        strat = await session.get(DraftStrategy, row.strategy_id)
        title = strat.title if strat else None
    return _to_read(row, strategy_title=title)


async def delete_draft(
    session: AsyncSession, *, owner_id: int, notebook_id: int
) -> None:
    await notebooks_svc.get_notebook(session, owner_id=owner_id, notebook_id=notebook_id)
    row = (
        await session.execute(
            select(NotebookKnowledgeDraft).where(
                NotebookKnowledgeDraft.notebook_id == notebook_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return
    await session.delete(row)
    await session.commit()


async def ask_about_point(
    session: AsyncSession,
    *,
    owner_id: int,
    notebook_id: int,
    body: KnowledgeDraftPointAskRequest,
) -> KnowledgeDraftPointAskResponse:
    """就某条要点的原句/主张做短问答（不投喂整字幕）。"""
    await notebooks_svc.get_notebook(session, owner_id=owner_id, notebook_id=notebook_id)
    row = (
        await session.execute(
            select(NotebookKnowledgeDraft).where(
                NotebookKnowledgeDraft.notebook_id == notebook_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("尚未生成知识底稿")

    content = _normalize_content(row.content_json if isinstance(row.content_json, dict) else {})
    point = next((p for p in content["points"] if p.get("id") == body.point_id), None)
    if point is None:
        raise NotFoundError("要点不存在")

    theme = str(content.get("theme") or "").strip()
    claim = str(point.get("text") or "").strip()
    evidence = str(point.get("evidence") or "").strip()
    example = str(point.get("example") or "").strip()
    if not evidence and not claim:
        raise BadRequestError("该要点缺少可追问的原句或主张")

    llm = await get_active_llm(session)
    provider = make_provider(
        provider_name=llm.provider,
        api_key=llm.api_key,
        base_url=llm.base_url,
        model_name=llm.model_name,
        params_json=llm.params_json,
    )

    system = (
        "你是视频知识学习助手。用户就「一条要点」提问。"
        "只依据给定的主题/主张/原句（及可选例子）回答，简洁、口语、中文，"
        "一般 3–8 句；不要编造视频里没有的时间戳或大段原文。"
    )
    ctx_lines = []
    if theme:
        ctx_lines.append(f"主题：{theme}")
    if claim:
        ctx_lines.append(f"主张：{claim}")
    if evidence:
        ctx_lines.append(f"原句：{evidence}")
    if example:
        ctx_lines.append(f"例子：{example}")
    ctx = "\n".join(ctx_lines)

    hist_bits: list[str] = []
    for m in (body.history or [])[-6:]:
        role = "用户" if m.role == "user" else "助手"
        hist_bits.append(f"{role}：{m.content.strip()}")
    hist_block = ("\n".join(hist_bits) + "\n") if hist_bits else ""

    user_prompt = (
        f"上下文：\n{ctx}\n\n"
        f"{hist_block}"
        f"用户问题：{body.message.strip()}\n\n"
        "请直接回答。"
    )

    try:
        answer = await provider.complete(user_prompt, system=system, max_tokens=1200)
    except Exception as exc:  # noqa: BLE001
        raise BadRequestError(f"模型调用失败：{exc}") from exc

    text = (answer or "").strip()
    if not text:
        raise BadRequestError("模型未返回有效回答")
    return KnowledgeDraftPointAskResponse(point_id=body.point_id, answer=text)

