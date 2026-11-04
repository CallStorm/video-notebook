"""按向量配置把笔记本拆成多段索引文本，并计算 content_hash。"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_draft import NotebookKnowledgeDraft
from app.models.notebook import (
    Note,
    Notebook,
    NotebookSource,
    Subtitle,
    SubtitleLine,
    Video,
)
from app.models.vector_settings import VectorSettingsConfig

# 硅基流动 BAAI/bge-m3 上限 8192 token。中文大约 1.1 万字还能嵌入，
# 默认 6000 字留余量。后台可改每一类的切割字数。
DEFAULT_CHUNK_CHARS = 6000
DEFAULT_CHUNK_OVERLAP = 200

_POINT_NS = uuid.UUID("6b0c1a2e-7f4d-4c1a-9b2e-0a6d5e4c3b21")
_PART_ORDER = (
    "title",
    "description",
    "overview",
    "subtitles",
    "notes",
    "conclusions",
    "draft",
)


@dataclass
class IndexChunk:
    key: str
    part: str
    text: str


@dataclass
class IndexDocument:
    chunks: list[IndexChunk]
    content_hash: str
    parts_used: list[str]

    @property
    def text(self) -> str:
        return "\n\n".join(chunk.text for chunk in self.chunks).strip()


def chunk_point_id(notebook_id: int, key: str) -> str:
    return str(uuid.uuid5(_POINT_NS, f"{int(notebook_id)}:{key}"))


def chunk_text_hash(text: str) -> str:
    return _sha256(text)


def split_text(text: str, limit: int, overlap: int) -> list[str]:
    """按字数切开。相邻段重叠 overlap 字，最后一段保留结尾。"""
    body = (text or "").strip()
    if not body:
        return []
    size = max(1, int(limit))
    if len(body) <= size:
        return [body]
    shared = max(0, min(int(overlap), size - 1))
    step = size - shared
    parts: list[str] = []
    start = 0
    while start < len(body):
        piece = body[start : start + size].strip()
        if piece:
            parts.append(piece)
        if start + size >= len(body):
            break
        start += step
    return parts


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _int_setting(settings: VectorSettingsConfig, name: str, default: int, *, minimum: int) -> int:
    raw = getattr(settings, name, None)
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value if value >= minimum else default


def _chunk_chars(settings: VectorSettingsConfig, name: str) -> int:
    return _int_setting(settings, name, DEFAULT_CHUNK_CHARS, minimum=1)


def _overlap(settings: VectorSettingsConfig) -> int:
    return _int_setting(settings, "chunk_overlap_chars", DEFAULT_CHUNK_OVERLAP, minimum=0)


def _windows(prefix: str, body: str, limit: int, overlap: int) -> list[str]:
    """每一段都带上 prefix，正文按 limit 扣除前缀后切开。"""
    label = prefix.strip()
    extra = len(label) + 1 if label else 0
    room = max(1, int(limit) - extra)
    shared = min(overlap, room - 1) if room > 1 else 0
    pieces = split_text(body, room, shared)
    if not label:
        return pieces
    return [f"{label}\n{piece}" for piece in pieces]


def _draft_body(raw: dict) -> str:
    """主题、概念、要点、收获、待问。勾选状态不进索引。"""
    lines: list[str] = []
    theme = str(raw.get("theme") or "").strip()
    if theme:
        lines.append(f"主题：{theme}")
    for item in raw.get("concepts") or []:
        if not isinstance(item, dict):
            continue
        term = str(item.get("term") or "").strip()
        definition = str(item.get("definition") or "").strip()
        piece = "：".join(part for part in (term, definition) if part)
        if piece:
            lines.append(f"概念：{piece}")
    for point in raw.get("points") or []:
        if not isinstance(point, dict):
            continue
        text = str(point.get("text") or "").strip()
        if text:
            lines.append(f"要点：{text}")
        for label, key in (("证据", "evidence"), ("例子", "example"), ("批注", "comment")):
            extra = str(point.get(key) or "").strip()
            if extra:
                lines.append(f"{label}：{extra}")
    for takeaway in raw.get("takeaways") or []:
        if isinstance(takeaway, dict):
            text = str(takeaway.get("text") or "").strip()
        else:
            text = str(takeaway or "").strip()
        if text:
            lines.append(f"收获：{text}")
    for question in raw.get("open_questions") or []:
        text = str(question or "").strip()
        if text:
            lines.append(f"待问：{text}")
    return "\n".join(lines)


def _add(chunks: list[IndexChunk], part: str, key: str, text: str) -> None:
    cleaned = text.strip()
    if cleaned:
        chunks.append(IndexChunk(key=key, part=part, text=cleaned))


def _add_windows(
    chunks: list[IndexChunk],
    *,
    part: str,
    key_prefix: str,
    text: str,
    limit: int,
    overlap: int,
) -> None:
    for index, window in enumerate(split_text(text, limit, overlap)):
        _add(chunks, part, f"{key_prefix}:{index}", window)


def _add_prefixed(
    chunks: list[IndexChunk],
    *,
    part: str,
    key_prefix: str,
    prefix: str,
    body: str,
    limit: int,
    overlap: int,
) -> None:
    for index, window in enumerate(_windows(prefix, body, limit, overlap)):
        _add(chunks, part, f"{key_prefix}:{index}", window)


async def build_notebook_document(
    session: AsyncSession,
    notebook: Notebook,
    settings: VectorSettingsConfig,
) -> IndexDocument:
    chunks: list[IndexChunk] = []
    seen: set[str] = set()
    overlap = _overlap(settings)
    card_limit = _chunk_chars(settings, "chunk_card_chars")
    subtitle_limit = _chunk_chars(settings, "chunk_subtitles_chars")
    note_limit = _chunk_chars(settings, "chunk_notes_chars")
    conclusion_limit = _chunk_chars(settings, "chunk_conclusions_chars")
    draft_limit = _chunk_chars(settings, "chunk_draft_chars")

    header_lines: list[str] = []
    if settings.index_title and (notebook.title or "").strip():
        header_lines.append(f"标题：{notebook.title.strip()}")
        seen.add("title")
    if settings.index_description and (notebook.description or "").strip():
        header_lines.append(f"描述：{notebook.description.strip()}")
        seen.add("description")
    header = "\n".join(header_lines)

    videos: list[Video] = []
    if settings.index_overview or settings.index_subtitles:
        video_ids = (
            await session.execute(
                select(NotebookSource.video_id).where(
                    NotebookSource.notebook_id == notebook.id
                )
            )
        ).scalars().all()
        if video_ids:
            videos = list(
                (
                    await session.execute(
                        select(Video).where(Video.id.in_(list(video_ids))).order_by(Video.id.asc())
                    )
                ).scalars().all()
            )

    source_blocks: list[str] = []
    if settings.index_overview:
        for video in videos:
            title = (video.title or "").strip()
            overview = (video.overview_text or "").strip()
            block: list[str] = []
            if title:
                block.append(f"来源：{title}")
            if overview:
                block.append(overview)
            if block:
                source_blocks.append("\n".join(block))
                seen.add("overview")

    if header or source_blocks:
        full = "\n\n".join(part for part in (header, "\n\n".join(source_blocks)) if part)
        if len(full) <= card_limit or not source_blocks:
            _add_windows(
                chunks,
                part="card",
                key_prefix="card",
                text=full,
                limit=card_limit,
                overlap=overlap,
            )
        else:
            for index, block in enumerate(source_blocks):
                piece = "\n\n".join(part for part in (header, block) if part)
                _add_windows(
                    chunks,
                    part="card",
                    key_prefix=f"card:{index}",
                    text=piece,
                    limit=card_limit,
                    overlap=overlap,
                )

    if settings.index_subtitles:
        for video in videos:
            sub = (
                await session.execute(
                    select(Subtitle)
                    .where(Subtitle.video_id == video.id)
                    .order_by(Subtitle.version.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if sub is None:
                continue
            lines = (
                await session.execute(
                    select(SubtitleLine.text)
                    .where(SubtitleLine.subtitle_id == sub.id)
                    .order_by(SubtitleLine.line_no.asc())
                )
            ).scalars().all()
            body = "\n".join(text.strip() for text in lines if text and text.strip())
            if not body:
                continue
            title = (video.title or "").strip()
            _add_prefixed(
                chunks,
                part="subtitles",
                key_prefix=f"subtitles:{video.id}",
                prefix=f"来源：{title}" if title else "字幕",
                body=body,
                limit=subtitle_limit,
                overlap=overlap,
            )
            seen.add("subtitles")

    if settings.index_notes:
        notes = (
            await session.execute(
                select(Note)
                .where(Note.notebook_id == notebook.id, Note.deleted_at.is_(None))
                .order_by(Note.id.asc())
            )
        ).scalars().all()
        for note in notes:
            title = (note.title or "").strip()
            body = (note.content_text or "").strip()
            if title and body:
                _add_prefixed(
                    chunks,
                    part="notes",
                    key_prefix=f"notes:{note.id}",
                    prefix=f"笔记：{title}",
                    body=body,
                    limit=note_limit,
                    overlap=overlap,
                )
            elif title or body:
                _add_windows(
                    chunks,
                    part="notes",
                    key_prefix=f"notes:{note.id}",
                    text=f"笔记：{title or body}",
                    limit=note_limit,
                    overlap=overlap,
                )
            else:
                continue
            seen.add("notes")

    if settings.index_conclusions or settings.index_draft:
        draft = (
            await session.execute(
                select(NotebookKnowledgeDraft).where(
                    NotebookKnowledgeDraft.notebook_id == notebook.id
                )
            )
        ).scalar_one_or_none()
        if draft is not None:
            raw = draft.content_json if isinstance(draft.content_json, dict) else {}
            if settings.index_conclusions:
                conclusions = raw.get("conclusions") if isinstance(raw, dict) else None
                lines: list[str] = []
                if isinstance(conclusions, list):
                    lines = [str(item).strip() for item in conclusions if str(item).strip()]
                if not lines and (draft.conclusion or "").strip():
                    lines = [
                        line.strip()
                        for line in draft.conclusion.splitlines()
                        if line.strip()
                    ]
                if lines:
                    _add_windows(
                        chunks,
                        part="conclusions",
                        key_prefix="conclusions",
                        text="我的结论：\n" + "\n".join(lines),
                        limit=conclusion_limit,
                        overlap=overlap,
                    )
                    seen.add("conclusions")
            if settings.index_draft:
                body = _draft_body(raw)
                if body:
                    _add_windows(
                        chunks,
                        part="draft",
                        key_prefix="draft",
                        text="知识底稿：\n" + body,
                        limit=draft_limit,
                        overlap=overlap,
                    )
                    seen.add("draft")

    parts_used = [name for name in _PART_ORDER if name in seen]
    flags = (
        f"t={int(bool(settings.index_title))};d={int(bool(settings.index_description))};"
        f"o={int(bool(settings.index_overview))};s={int(bool(settings.index_subtitles))};"
        f"n={int(bool(settings.index_notes))};c={int(bool(settings.index_conclusions))};"
        f"g={int(bool(settings.index_draft))};"
        f"card={card_limit};sub={subtitle_limit};note={note_limit};"
        f"con={conclusion_limit};draft={draft_limit};ov={overlap};"
        f"share={int(bool(notebook.share_all))}"
    )
    body = "\n".join(f"{chunk.key}\n{chunk.text}" for chunk in chunks)
    return IndexDocument(
        chunks=chunks,
        content_hash=_sha256(flags + "\n" + body),
        parts_used=parts_used,
    )
