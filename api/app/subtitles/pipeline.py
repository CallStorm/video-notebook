"""上传完成后的字幕任务。

顺序：内嵌字幕轨 → 后台默认语音转文字。开发期在 API 进程里跑，
不依赖单独的 Celery worker。测试环境不自动启动，避免打到外网。
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import BadRequestError, NotFoundError
from app.db.session import get_sessionmaker
from app.llm.config_service import get_active_stt
from app.models.notebook import Video
from app.services.sources import get_video
from app.storage import get_storage
from app.subtitles.media import MediaError, extract_embedded_cues, prepare_audio
from app.subtitles.overview import write_overview
from app.subtitles.srt import Cue
from app.subtitles.store import load_subtitle, replace_subtitle, subtitle_view
from app.subtitles.transcribe import TranscribeError, transcribe_file

logger = logging.getLogger(__name__)

_running: set[int] = set()
_lock = asyncio.Lock()


def job_running(video_id: int) -> bool:
    return video_id in _running


def kick_subtitle_job(video_id: int, *, force: bool = False) -> None:
    """请求返回后继续跑。force=True 用于「重新生成」，忽略 pending 状态。"""
    if get_settings().app_env == "test":
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("no running loop, skip subtitle job video_id=%s", video_id)
        return
    loop.create_task(_guarded(video_id, force=force))


async def read_subtitle_for_owner(
    session: AsyncSession, *, owner_id: int, video_id: int
) -> dict:
    video = await get_video(session, owner_id=owner_id, video_id=video_id)
    subtitle, lines = await load_subtitle(session, video)
    return subtitle_view(video, subtitle, lines)


async def request_regenerate(
    session: AsyncSession, *, owner_id: int, video_id: int
) -> dict:
    video = await get_video(session, owner_id=owner_id, video_id=video_id)
    if not video.storage_key:
        raise BadRequestError("视频还没保存到本地，暂时无法生成字幕")
    if get_settings().app_env == "test":
        subtitle, lines = await load_subtitle(session, video)
        return subtitle_view(video, subtitle, lines)
    if job_running(video.id):
        subtitle, lines = await load_subtitle(session, video)
        return subtitle_view(video, subtitle, lines)
    video.subtitle_status = "processing"
    video.subtitle_error = None
    video.overview_status = "processing"
    video.overview_error = None
    session.add(video)
    await session.commit()
    await session.refresh(video)
    kick_subtitle_job(video.id, force=True)
    subtitle, lines = await load_subtitle(session, video)
    return subtitle_view(video, subtitle, lines)


async def run_subtitle_pipeline(
    video_id: int, *, session: AsyncSession | None = None
) -> None:
    """生成字幕并覆盖写入。传入 session 时全程复用它（测试用）。"""

    async def _use(fn: Callable[[AsyncSession], Awaitable[None]]) -> None:
        if session is not None:
            try:
                await fn(session)
            except Exception:
                await session.rollback()
                raise
            return
        async with get_sessionmaker()() as owned:
            await fn(owned)

    path_holder: dict[str, Path] = {}

    async def _mark_processing(db: AsyncSession) -> None:
        video = await db.get(Video, video_id)
        if video is None or not video.storage_key:
            return
        video.subtitle_status = "processing"
        video.subtitle_error = None
        db.add(video)
        await db.commit()
        path_holder["path"] = _local_path(video.storage_key)

    await _use(_mark_processing)
    path = path_holder.get("path")
    if path is None:
        return

    async def _write_overview_if_requested(db: AsyncSession) -> None:
        """只有「重新生成」会把 overview_status 设成 processing。普通上传不写概览。"""
        video = await db.get(Video, video_id)
        if video is None or video.overview_status != "processing":
            return
        try:
            _subtitle, lines = await load_subtitle(db, video)
            video.overview_text = await write_overview(db, lines)
            video.overview_status = "ready"
            video.overview_error = None
        except Exception as exc:  # noqa: BLE001 — 概览失败不能把已经写好的字幕打回失败
            logger.warning("overview failed video_id=%s: %s", video_id, exc)
            video.overview_status = "failed"
            video.overview_error = str(exc)[:2000]
        db.add(video)
        await db.commit()

    try:
        embedded = await asyncio.to_thread(extract_embedded_cues, path)
        if embedded is not None:
            cues, language = embedded
            origin = "embedded"
        else:
            cues, language = await _transcribe(path, session)
            origin = "asr"
        if not cues:
            raise TranscribeError("没有识别到字幕")

        async def _save(db: AsyncSession) -> None:
            video = await db.get(Video, video_id)
            if video is None:
                return
            await replace_subtitle(
                db, video, cues, source=origin, language=language
            )

        await _use(_save)
        await _use(_write_overview_if_requested)
    except Exception as exc:  # noqa: BLE001 — 失败要写回状态，不能把任务吞掉后一直停在 processing
        message = _error_message(exc)
        logger.warning("subtitle pipeline failed video_id=%s: %s", video_id, message)

        async def _fail(db: AsyncSession) -> None:
            video = await db.get(Video, video_id)
            if video is None:
                return
            video.subtitle_status = "failed"
            video.subtitle_error = message[:2000]
            if video.overview_status == "processing":
                video.overview_status = "failed"
                video.overview_error = "字幕生成失败，概览未生成"
            db.add(video)
            await db.commit()

        await _use(_fail)


async def _transcribe(
    path: Path, session: AsyncSession | None
) -> tuple[list[Cue], str | None]:
    if session is not None:
        stt = await get_active_stt(session)
    else:
        async with get_sessionmaker()() as owned:
            stt = await get_active_stt(owned)

    audio = await asyncio.to_thread(prepare_audio, path)
    try:
        return await transcribe_file(stt, str(audio))
    finally:
        if audio != path:
            audio.unlink(missing_ok=True)


async def _guarded(video_id: int, *, force: bool) -> None:
    async with _lock:
        if video_id in _running:
            return
        _running.add(video_id)
    try:
        if not force:
            async with get_sessionmaker()() as db:
                video = await db.get(Video, video_id)
                if video is None or not video.storage_key or video.subtitle_status != "pending":
                    return
        await run_subtitle_pipeline(video_id)
    except Exception:
        logger.exception("subtitle job crashed video_id=%s", video_id)
    finally:
        async with _lock:
            _running.discard(video_id)


def _local_path(key: str) -> Path:
    storage = get_storage()
    root = Path(storage.root)  # type: ignore[attr-defined]
    sha1 = key.split(".", 1)[0]
    suffix = key[len(sha1) :]
    return root / sha1[:2] / f"{sha1}{suffix}"


def _error_message(exc: Exception) -> str:
    if isinstance(exc, (MediaError, TranscribeError, BadRequestError, NotFoundError)):
        return str(exc)
    return f"字幕生成失败: {exc.__class__.__name__}: {exc}"
