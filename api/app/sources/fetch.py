"""Background URL fetch job (in-process asyncio, like subtitle pipeline)."""
from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_sessionmaker
from app.models.notebook import Video
from app.sources.ytdlp import FetchDownloadError, download_url
from app.storage import get_storage

logger = logging.getLogger(__name__)

_running: set[int] = set()
_lock = asyncio.Lock()


@dataclass
class _Bundle:
    work_dir: Path
    video_path: Path
    title: str | None
    subtitle_path: Path | None
    subtitle_language: str | None


def job_running(video_id: int) -> bool:
    return video_id in _running


def kick_fetch_job(video_id: int) -> None:
    """Start URL download after the request returns. Skipped in test env."""
    if get_settings().app_env == "test":
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("no running loop, skip fetch job video_id=%s", video_id)
        return
    loop.create_task(_guarded(video_id))


async def run_fetch_pipeline(
    video_id: int, *, session: AsyncSession | None = None
) -> None:
    """Download URL source into storage and mark ready / failed."""

    async def _use(fn):
        if session is not None:
            try:
                await fn(session)
            except Exception:
                await session.rollback()
                raise
            return
        async with get_sessionmaker()() as owned:
            await fn(owned)

    url_holder: dict[str, str] = {}

    async def _mark_probing(db: AsyncSession) -> None:
        video = await db.get(Video, video_id)
        if video is None or video.source_type != "url" or not video.source_url:
            return
        if video.status == "ready" and video.storage_key:
            return
        video.status = "probing"
        video.error_message = None
        db.add(video)
        await db.commit()
        url_holder["url"] = video.source_url

    await _use(_mark_probing)
    url = url_holder.get("url")
    if not url:
        return

    result: _Bundle | None = None
    try:
        result = await asyncio.to_thread(_download_into_temp, url)
    except Exception as exc:  # noqa: BLE001
        message = _error_message(exc)
        logger.warning("fetch download failed video_id=%s: %s", video_id, message)

        async def _fail(db: AsyncSession) -> None:
            video = await db.get(Video, video_id)
            if video is None:
                return
            video.status = "failed"
            video.error_message = message[:2000]
            db.add(video)
            await db.commit()

        await _use(_fail)
        return

    try:
        async def _ok(db: AsyncSession) -> None:
            assert result is not None
            await _persist_success(db, video_id, result)

        await _use(_ok)
    except Exception as exc:  # noqa: BLE001
        message = _error_message(exc)
        logger.exception("fetch persist failed video_id=%s", video_id)

        async def _fail2(db: AsyncSession) -> None:
            video = await db.get(Video, video_id)
            if video is None:
                return
            video.status = "failed"
            video.error_message = message[:2000]
            db.add(video)
            await db.commit()

        await _use(_fail2)
        return
    finally:
        if result is not None:
            _cleanup_work(result.work_dir)

    async def _maybe_subtitle(db: AsyncSession) -> None:
        video = await db.get(Video, video_id)
        if video is None or not video.storage_key:
            return
        if video.subtitle_status == "ready":
            return
        from app.subtitles.pipeline import kick_subtitle_job

        kick_subtitle_job(video.id)

    await _use(_maybe_subtitle)


def _download_into_temp(url: str) -> _Bundle:
    work_dir = Path(tempfile.mkdtemp(prefix="vnb-fetch-"))
    try:
        downloaded = download_url(url, work_dir)
    except Exception:
        _cleanup_work(work_dir)
        raise
    return _Bundle(
        work_dir=work_dir,
        video_path=downloaded.video_path,
        title=downloaded.title,
        subtitle_path=downloaded.subtitle_path,
        subtitle_language=downloaded.subtitle_language,
    )


async def _persist_success(db: AsyncSession, video_id: int, result: _Bundle) -> None:
    from app.services.sources import _ffprobe, _suffix_from_filename
    from app.subtitles.srt import parse_srt
    from app.subtitles.store import replace_subtitle

    video = await db.get(Video, video_id)
    if video is None:
        return

    data = result.video_path.read_bytes()
    suffix = _suffix_from_filename(result.video_path.name) or ".mp4"
    mime = "video/mp4" if suffix == ".mp4" else f"video/{suffix.lstrip('.')}"
    storage = get_storage()
    key = storage.put(data=data, content_type=mime, suffix=suffix)
    info = storage.head(key)
    content_hash = key.split(".", 1)[0]

    existing = (
        await db.execute(
            select(Video).where(
                Video.owner_id == video.owner_id,
                Video.content_hash == content_hash,
                Video.id != video.id,
            )
        )
    ).scalar_one_or_none()

    if existing is not None and existing.storage_key:
        video.storage_key = existing.storage_key
        # Avoid unique (owner_id, content_hash) collision on this new row.
        video.content_hash = None
        video.mime = existing.mime or mime
        video.size_bytes = existing.size_bytes or (info.size if info else len(data))
        video.duration_ms = existing.duration_ms
        video.width = existing.width
        video.height = existing.height
    else:
        video.storage_key = key
        video.content_hash = content_hash
        video.mime = mime
        video.size_bytes = info.size if info else len(data)
        try:
            meta = await asyncio.to_thread(_ffprobe, key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ffprobe after fetch failed video_id=%s: %s", video_id, exc)
            meta = None
        if meta:
            video.duration_ms = meta.get("duration_ms")
            video.width = meta.get("width")
            video.height = meta.get("height")

    if result.title:
        video.title = result.title[:255]
    video.status = "ready"
    video.error_message = None
    db.add(video)
    await db.commit()
    await db.refresh(video)

    if result.subtitle_path and result.subtitle_path.exists():
        try:
            cues = parse_srt(
                result.subtitle_path.read_text(encoding="utf-8", errors="replace")
            )
            if cues:
                await replace_subtitle(
                    db,
                    video,
                    cues,
                    source="platform",
                    language=result.subtitle_language,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "platform subtitle import failed video_id=%s: %s", video_id, exc
            )


async def _guarded(video_id: int) -> None:
    async with _lock:
        if video_id in _running:
            return
        _running.add(video_id)
    try:
        async with get_sessionmaker()() as db:
            video = await db.get(Video, video_id)
            if video is None or video.source_type != "url":
                return
            if video.status == "ready" and video.storage_key:
                return
        await run_fetch_pipeline(video_id)
    except Exception:
        logger.exception("fetch job crashed video_id=%s", video_id)
    finally:
        async with _lock:
            _running.discard(video_id)


def _cleanup_work(work_dir: Path | None) -> None:
    if work_dir is None:
        return
    shutil.rmtree(work_dir, ignore_errors=True)


def _error_message(exc: Exception) -> str:
    if isinstance(exc, FetchDownloadError):
        return f"抓取失败: {exc}"
    return f"抓取失败: {exc.__class__.__name__}: {exc}"
