"""按向量配置拼笔记本索引文档文本 + content_hash。"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notebook import (
    Note,
    Notebook,
    NotebookSource,
    Subtitle,
    SubtitleLine,
    Video,
)
from app.models.vector_settings import VectorSettingsConfig


@dataclass
class IndexDocument:
    text: str
    content_hash: str
    parts_used: list[str]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def build_notebook_document(
    session: AsyncSession,
    notebook: Notebook,
    settings: VectorSettingsConfig,
) -> IndexDocument:
    chunks: list[str] = []
    parts: list[str] = []

    if settings.index_title and notebook.title:
        chunks.append(f"标题：{notebook.title.strip()}")
        parts.append("title")
    if settings.index_description and (notebook.description or "").strip():
        chunks.append(f"描述：{notebook.description.strip()}")
        parts.append("description")

    if settings.index_overview or settings.index_subtitles:
        video_ids = (
            await session.execute(
                select(NotebookSource.video_id).where(
                    NotebookSource.notebook_id == notebook.id
                )
            )
        ).scalars().all()
        if video_ids:
            videos = (
                await session.execute(select(Video).where(Video.id.in_(list(video_ids))))
            ).scalars().all()
            for v in videos:
                if settings.index_overview:
                    title = (v.title or "").strip()
                    overview = (v.overview_text or "").strip()
                    if title or overview:
                        block = []
                        if title:
                            block.append(f"来源：{title}")
                        if overview:
                            block.append(overview)
                        chunks.append("\n".join(block))
                        if "overview" not in parts:
                            parts.append("overview")
                if settings.index_subtitles:
                    sub = (
                        await session.execute(
                            select(Subtitle)
                            .where(Subtitle.video_id == v.id)
                            .order_by(Subtitle.version.desc())
                            .limit(1)
                        )
                    ).scalar_one_or_none()
                    if sub is not None:
                        lines = (
                            await session.execute(
                                select(SubtitleLine.text)
                                .where(SubtitleLine.subtitle_id == sub.id)
                                .order_by(SubtitleLine.line_no.asc())
                                .limit(2000)
                            )
                        ).scalars().all()
                        body = "\n".join(t.strip() for t in lines if t and t.strip())
                        if body:
                            chunks.append(body[:20000])
                            if "subtitles" not in parts:
                                parts.append("subtitles")

    if settings.index_notes:
        notes = (
            await session.execute(
                select(Note)
                .where(Note.notebook_id == notebook.id, Note.deleted_at.is_(None))
                .order_by(Note.id.asc())
                .limit(100)
            )
        ).scalars().all()
        for n in notes:
            title = (n.title or "").strip()
            body = (n.content_text or "").strip()
            piece = f"{title}\n{body}".strip()
            if piece:
                chunks.append(piece[:8000])
        if notes:
            parts.append("notes")

    text = "\n\n".join(c for c in chunks if c).strip()
    flags = (
        f"t={int(settings.index_title)};d={int(settings.index_description)};"
        f"o={int(settings.index_overview)};s={int(settings.index_subtitles)};"
        f"n={int(settings.index_notes)}"
    )
    content_hash = _sha256(flags + "\n" + text)
    return IndexDocument(text=text, content_hash=content_hash, parts_used=parts)
