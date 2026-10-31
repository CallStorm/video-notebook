"""把勾选来源的整段字幕编成带编号的上下文。v1 不做检索；不截断勾选全文。"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notebook import NotebookSource, SubtitleLine, Video
from app.subtitles.store import load_subtitle

# 默认上下文字符预算；运行时以 chat_settings_config.max_context_chars 为准。
MAX_CONTEXT_CHARS = 60_000
_CITE_RE = re.compile(r"\[(\d+)\]")


@dataclass(frozen=True)
class CitedLine:
    n: int
    video_id: int
    line_no: int
    snippet: str
    title: str | None


@dataclass(frozen=True)
class BuiltContext:
    text: str
    lines: dict[int, CitedLine]
    source_ids: list[int]
    truncated: bool
    chars: int


async def build_context(
    session: AsyncSession,
    *,
    notebook_id: int,
    source_ids: list[int],
) -> BuiltContext:
    """始终编入勾选来源全文（编号字幕）。不做中途截断。"""
    if not source_ids:
        return BuiltContext(text="", lines={}, source_ids=[], truncated=False, chars=0)
    stmt = (
        select(NotebookSource, Video)
        .join(Video, Video.id == NotebookSource.video_id)
        .where(
            NotebookSource.notebook_id == notebook_id,
            NotebookSource.video_id.in_(source_ids),
        )
        .order_by(NotebookSource.sort, NotebookSource.video_id)
    )
    rows = (await session.execute(stmt)).all()
    parts: list[str] = []
    lines: dict[int, CitedLine] = {}
    used_ids: list[int] = []
    used_chars = 0
    n = 1
    for _source, video in rows:
        block = _source_block(video, await _lines(session, video), n)
        if block is None:
            continue
        text, added, next_n = block
        for item in added:
            lines[item.n] = item
        parts.append(text)
        used_ids.append(video.id)
        used_chars += len(text)
        n = next_n
    return BuiltContext(
        text="\n\n".join(parts),
        lines=lines,
        source_ids=used_ids,
        truncated=False,
        chars=used_chars,
    )


async def _lines(session: AsyncSession, video: Video) -> list[SubtitleLine]:
    _subtitle, subtitle_lines = await load_subtitle(session, video)
    return subtitle_lines


def parse_citations(text: str, lines: dict[int, CitedLine]) -> list[dict]:
    found: list[dict] = []
    seen: set[int] = set()
    for match in _CITE_RE.finditer(text):
        n = int(match.group(1))
        if n in seen or n not in lines:
            continue
        seen.add(n)
        item = lines[n]
        found.append(
            {
                "n": item.n,
                "source_id": item.video_id,
                "line_no": item.line_no,
                "snippet": item.snippet,
                "title": item.title,
            }
        )
    return found


def strip_citations(text: str) -> str:
    """去掉正文里的 [n] 引用标记，并理顺留下的空白。"""
    cleaned = _CITE_RE.sub("", text)
    cleaned = re.sub(r"[ \t]+([，。！？、；：,.!?])", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    return cleaned.strip()


def _source_block(
    video: Video,
    subtitle_lines: list[SubtitleLine],
    start_n: int,
) -> tuple[str, list[CitedLine], int] | None:
    title = (video.title or "").strip() or f"来源 {video.id}"
    header = f"来源：{title}"
    body: list[str] = []
    added: list[CitedLine] = []
    n = start_n
    for line in subtitle_lines:
        piece = (line.text or "").strip()
        if not piece:
            continue
        rendered = f"[{n}] {piece}"
        body.append(rendered)
        added.append(
            CitedLine(
                n=n,
                video_id=video.id,
                line_no=line.line_no,
                snippet=piece[:120],
                title=title,
            )
        )
        n += 1
    if not body:
        return None
    return header + "\n" + "\n".join(body), added, n
