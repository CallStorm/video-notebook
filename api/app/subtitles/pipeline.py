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
from app.observability.pipeline_log import log_event, pipeline_stage

logger = logging.getLogger(__name__)


def job_running(video_id: int) -> bool:
    """Subtitle runs on the media worker; API process no longer tracks in-flight jobs."""
    return False


def kick_subtitle_job(video_id: int, *, force: bool = False, notebook_id: int | None = None) -> None:
    """Enqueue subtitle pipeline on the media worker (shares concurrency slots)."""
    from app.media.enqueue import enqueue_pipeline

    enqueue_pipeline(video_id, stage="subtitle_only", force=force, notebook_id=notebook_id)


async def read_subtitle_for_owner(
    session: AsyncSession, *, owner_id: int, video_id: int
) -> dict:
    video = await get_video(session, owner_id=owner_id, video_id=video_id)
    subtitle, lines = await load_subtitle(session, video)
    return subtitle_view(video, subtitle, lines)


async def read_subtitle_for_viewer(
    session: AsyncSession, *, viewer_id: int, video_id: int
) -> dict:
    from app.services.sources import get_video_readable

    video = await get_video_readable(session, viewer_id=viewer_id, video_id=video_id)
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
    from app.models.notebook import NotebookSource
    from sqlalchemy import select as _select

    nb_id = await session.scalar(
        _select(NotebookSource.notebook_id)
        .where(NotebookSource.video_id == video.id)
        .limit(1)
    )
    kick_subtitle_job(video.id, force=True, notebook_id=nb_id)
    subtitle, lines = await load_subtitle(session, video)
    return subtitle_view(video, subtitle, lines)



async def run_overview_if_needed(
    video_id: int, *, session: AsyncSession | None = None, notebook_id: int | None = None
) -> None:
    """字幕已 ready 时：按设置自动写概览，或 overview 已是 processing 时强制写。

    平台字幕捷径跳过 run_subtitle_pipeline 时也走这里，避免概览永远 pending。
    """

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

    async def _arm_and_write(db: AsyncSession) -> None:
        from app.services.overview_settings import get_overview_settings_row

        video = await db.get(Video, video_id)
        if video is None:
            return
        if video.subtitle_status != "ready":
            return

        if video.overview_status != "processing":
            settings = await get_overview_settings_row(db)
            auto = bool(settings.auto_generate_after_subtitle)
            empty_text = not (video.overview_text or "").strip()
            should_auto = auto and (
                video.overview_status == "pending"
                or (empty_text and video.overview_status != "ready")
            )
            if not should_auto:
                # Incremental / already-done path: always emit so UI is not "未执行".
                if video.overview_status == "ready" and not empty_text:
                    log_event(
                        "overview",
                        "skipped",
                        summary="overview already ready",
                        detail={"video_id": video_id},
                    )
                elif not auto:
                    log_event(
                        "overview",
                        "skipped",
                        summary="auto generate disabled",
                        detail={
                            "video_id": video_id,
                            "overview_status": video.overview_status,
                        },
                    )
                else:
                    log_event(
                        "overview",
                        "skipped",
                        summary=f"overview status={video.overview_status}",
                        detail={"video_id": video_id},
                    )
                return
            video.overview_status = "processing"
            video.overview_error = None
            db.add(video)
            await db.commit()
            await db.refresh(video)

        with pipeline_stage("overview", summary="generate source overview"):
            try:
                _subtitle, lines = await load_subtitle(db, video)
                nb_id = notebook_id
                if nb_id is None:
                    from sqlalchemy import select as _select

                    from app.models.notebook import NotebookSource

                    nb_id = await db.scalar(
                        _select(NotebookSource.notebook_id)
                        .where(NotebookSource.video_id == video.id)
                        .order_by(NotebookSource.notebook_id.asc())
                        .limit(1)
                    )
                video.overview_text = await write_overview(
                    db, lines, video=video, notebook_id=nb_id
                )
                video.overview_status = "ready"
                video.overview_error = None
            except Exception as exc:  # noqa: BLE001
                logger.warning("overview failed video_id=%s: %s", video_id, exc)
                video.overview_status = "failed"
                video.overview_error = str(exc)[:2000]
                raise
            finally:
                db.add(video)
                await db.commit()

    try:
        await _use(_arm_and_write)
    except Exception:
        # overview failure already persisted; do not bubble for platform shortcut
        # (caller may ignore). For regenerate path we still don't fail subtitle.
        return


async def run_subtitle_pipeline(
    video_id: int,
    *,
    session: AsyncSession | None = None,
    notebook_id: int | None = None,
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

    try:
        with pipeline_stage("subtitle", summary="extract or ASR"):
            embedded = await asyncio.to_thread(extract_embedded_cues, path)
            if embedded is not None:
                cues, language = embedded
                origin = "embedded"
            else:
                with pipeline_stage("asr", summary="speech-to-text"):
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
        await run_overview_if_needed(
            video_id, session=session, notebook_id=notebook_id
        )
    except Exception as exc:  # noqa: BLE001 — 失败要写回状态，不能把任务吞掉后一直停在 processing
        try:
            from celery.exceptions import SoftTimeLimitExceeded as _SoftLimit
        except Exception:  # pragma: no cover
            _SoftLimit = ()  # type: ignore[assignment,misc]
        if _SoftLimit and isinstance(exc, _SoftLimit):
            raise
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
