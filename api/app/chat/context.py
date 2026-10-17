"""把勾选来源的整段字幕编成带编号的上下文。v1 不做检索。"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notebook import NotebookSource, SubtitleLine, Video
from app.subtitles.store import load_subtitle

# 大约按字符估。超出后截断，并在回答前提示。
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
    truncated = False
    n = 1
    for _source, video in rows:
        _subtitle, subtitle_lines = await load_subtitle(session, video)
        block = _source_block(video, subtitle_lines, n, used_chars)
        if block is None:
            continue
        text, added, next_n, hit_limit = block
        for item in added:
            lines[item.n] = item
        if text:
            parts.append(text)
            used_ids.append(video.id)
            used_chars += len(text)
        n = next_n
        if hit_limit:
            truncated = True
            break
    return BuiltContext(
        text="\n\n".join(parts),
        lines=lines,
        source_ids=used_ids,
        truncated=truncated,
        chars=used_chars,
    )


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
    return _CITE_RE.sub("", text).strip()


def _source_block(
    video: Video,
    subtitle_lines: list[SubtitleLine],
    start_n: int,
    used_chars: int,
) -> tuple[str, list[CitedLine], int, bool] | None:
    title = (video.title or "").strip() or f"来源 {video.id}"
    header = f"来源：{title}"
    body: list[str] = []
    added: list[CitedLine] = []
    n = start_n
    chars = used_chars + len(header)
    hit_limit = False
    for line in subtitle_lines:
        piece = (line.text or "").strip()
        if not piece:
            continue
        rendered = f"[{n}] {piece}"
        if chars + len(rendered) + 1 > MAX_CONTEXT_CHARS:
            hit_limit = True
            break
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
        chars += len(rendered) + 1
        n += 1
    if not body:
        return None
    return header + "\n" + "\n".join(body), added, n, hit_limit
