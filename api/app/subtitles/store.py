"""字幕行的读取和覆盖写入。重新转写成功前不删旧行。"""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notebook import Subtitle, SubtitleLine, Video
from app.storage import get_storage
from app.subtitles.srt import Cue, format_srt


def subtitle_view(video: Video, subtitle: Subtitle | None, lines: list[SubtitleLine]) -> dict:
    return {
        "video_id": video.id,
        "subtitle_status": video.subtitle_status,
        "subtitle_error": video.subtitle_error,
        "source": subtitle.source if subtitle else None,
        "language": subtitle.language if subtitle else None,
        "line_count": subtitle.line_count if subtitle else 0,
        "lines": [
            {
                "line_no": line.line_no,
                "start_ms": line.start_ms,
                "end_ms": line.end_ms,
                "text": line.text,
            }
            for line in lines
        ],
    }


async def load_subtitle(
    session: AsyncSession, video: Video
) -> tuple[Subtitle | None, list[SubtitleLine]]:
    subtitle = (
        await session.execute(
            select(Subtitle)
            .where(Subtitle.video_id == video.id)
            .order_by(Subtitle.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if subtitle is None:
        return None, []
    lines = (
        await session.execute(
            select(SubtitleLine)
            .where(SubtitleLine.subtitle_id == subtitle.id)
            .order_by(SubtitleLine.line_no)
        )
    ).scalars().all()
    return subtitle, list(lines)


async def replace_subtitle(
    session: AsyncSession,
    video: Video,
    cues: list[Cue],
    *,
    source: str,
    language: str | None,
) -> Subtitle:
    """成功后覆盖旧字幕。旧行在这次提交之前一直还在。"""
    existing_ids = select(Subtitle.id).where(Subtitle.video_id == video.id)
    await session.execute(
        delete(SubtitleLine).where(SubtitleLine.subtitle_id.in_(existing_ids))
    )
    await session.execute(delete(Subtitle).where(Subtitle.video_id == video.id))

    srt = format_srt(cues)
    storage_key = get_storage().put(
        data=srt.encode("utf-8"),
        content_type="application/x-subrip",
        suffix=".srt",
    )
    subtitle = Subtitle(
        video_id=video.id,
        source=source,
        language=(language or None),
        format="srt",
        storage_key=storage_key,
        line_count=len(cues),
        version=1,
    )
    session.add(subtitle)
    await session.flush()
    for index, cue in enumerate(cues, start=1):
        session.add(
            SubtitleLine(
                subtitle_id=subtitle.id,
                line_no=index,
                start_ms=cue.start_ms,
                end_ms=cue.end_ms,
                text=cue.text,
            )
        )
    video.subtitle_status = "ready"
    video.subtitle_error = None
    session.add(video)
    await session.commit()
    await session.refresh(subtitle)
    return subtitle
