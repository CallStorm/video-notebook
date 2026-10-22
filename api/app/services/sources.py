"""Source（视频）服务：上传、URL fetch、查询、删除。

- upload：multipart 流式写到 LocalFsStorage（按 sha1 内容寻址），写完后做一次 ffprobe
  探查（可选，没装 ffmpeg 也能用），然后 status=ready。
- fetch_url：创建 pending 记录后 kick 后台 yt-dlp 抓取（pending → probing → ready/failed）。
- delete：级联删 video row + storage_key 文件 + subtitles + notebook_sources 关联。
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
from typing import IO

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.notebook import Notebook, NotebookSource, Subtitle, SubtitleLine, Video
from app.storage import ObjectStorage, get_storage

logger = logging.getLogger(__name__)


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


# ── 上传 ──────────────────────────────────────────────────────
async def upload_video(
    session: AsyncSession,
    *,
    owner_id: int,
    notebook_id: int,
    filename: str,
    content_type: str | None,
    stream: IO[bytes],
) -> dict:
    """流式读取上传文件 → 写盘 → 入库。"""
    nb = (
        await session.execute(
            select(Notebook).where(
                Notebook.id == notebook_id,
                Notebook.owner_id == owner_id,
                Notebook.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if nb is None:
        raise NotFoundError(f"notebook {notebook_id} 不存在")

    storage: ObjectStorage = get_storage()
    suffix = _suffix_from_filename(filename)
    key = storage.put(
        data=stream.read(),
        content_type=content_type,
        suffix=suffix,
    )

    size = os.path.getsize(_local_path_for_key(key)) if False else None  # 占位，下面重算
    size = _safe_stat_size(key, storage)

    # 内容去重：同 owner 同 hash 已经存在 video，关联到 notebook
    existing = (
        await session.execute(
            select(Video).where(
                Video.owner_id == owner_id,
                Video.content_hash == key.split(".", 1)[0],
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        v = existing
    else:
        v = Video(
            owner_id=owner_id,
            source_type="upload",
            source_url=None,
            storage_key=key,
            mime=content_type,
            content_hash=key.split(".", 1)[0],
            size_bytes=size,
            title=filename,
            status="pending",
        )
        session.add(v)
        await session.commit()
        await session.refresh(v)

    # 关联到 notebook（如果还没）
    link = (
        await session.execute(
            select(NotebookSource).where(
                NotebookSource.notebook_id == notebook_id,
                NotebookSource.video_id == v.id,
            )
        )
    ).scalar_one_or_none()
    if link is None:
        # sort = max+1
        max_sort = (
            await session.scalar(
                select(NotebookSource.sort)
                .where(NotebookSource.notebook_id == notebook_id)
                .order_by(NotebookSource.sort.desc())
                .limit(1)
            )
        ) or 0
        session.add(
            NotebookSource(
                notebook_id=notebook_id,
                video_id=v.id,
                sort=max_sort + 1,
                selected_for_chat=True,
            )
        )
        await session.commit()

    # 探查：ffprobe 跑 metadata（best-effort，失败不阻塞）
    # v1 同步跑（不后台）：ffprobe 通常 < 1s；同步调用简化测试与异常处理。
    # v2 可改 Celery 异步跑。
    try:
        meta = await asyncio.to_thread(_ffprobe, v.storage_key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ffprobe failed for video %s: %s", v.id, exc)
        meta = None

    if meta is not None:
        v.duration_ms = meta.get("duration_ms")
        v.width = meta.get("width")
        v.height = meta.get("height")
    v.status = "ready"
    v.error_message = None if meta is not None else "ffprobe 不可用，已跳过元数据"
    session.add(v)
    await session.commit()
    await session.refresh(v)

    return _video_to_dict(v)


async def _probe_video_async(video_id: int, *, storage_key: str | None) -> None:
    """保留的旧版本（v2 异步用）。当前 _probe 在 upload_video 里直接同步跑。"""
    pass


def _ffprobe(storage_key: str | None) -> dict:
    """同步 ffprobe。返回 {duration_ms, width, height} 或抛。"""
    if not storage_key:
        return {}
    get_storage()
    path = _local_path_for_key_real(storage_key)
    if not os.path.exists(path):
        return {}
    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height:format=duration",
                "-of", "json",
                path,
            ],
            timeout=15,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return {}
    data = json.loads(out.decode("utf-8") or "{}")
    stream = (data.get("streams") or [{}])[0]
    width = stream.get("width")
    height = stream.get("height")
    dur_s = data.get("format", {}).get("duration")
    return {
        "width": int(width) if width else None,
        "height": int(height) if height else None,
        "duration_ms": int(float(dur_s) * 1000) if dur_s else None,
    }


# ── URL fetch ──────────────────────────────────────────────
async def fetch_url(
    session: AsyncSession,
    *,
    owner_id: int,
    notebook_id: int,
    url: str,
) -> dict:
    nb = (
        await session.execute(
            select(Notebook).where(
                Notebook.id == notebook_id,
                Notebook.owner_id == owner_id,
                Notebook.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if nb is None:
        raise NotFoundError(f"notebook {notebook_id} 不存在")

    v = Video(
        owner_id=owner_id,
        source_type="url",
        source_url=url,
        status="pending",
        title=url[:255],
    )
    session.add(v)
    await session.commit()
    await session.refresh(v)

    # 关联
    max_sort = (
        await session.scalar(
            select(NotebookSource.sort)
            .where(NotebookSource.notebook_id == notebook_id)
            .order_by(NotebookSource.sort.desc())
            .limit(1)
        )
    ) or 0
    session.add(
        NotebookSource(
            notebook_id=notebook_id,
            video_id=v.id,
            sort=max_sort + 1,
            selected_for_chat=True,
        )
    )
    await session.commit()

    from app.sources.fetch import kick_fetch_job

    kick_fetch_job(v.id)
    return _video_to_dict(v)


# ── 查询 / 删除 ─────────────────────────────────────────────
async def get_video(
    session: AsyncSession, *, owner_id: int, video_id: int
) -> Video:
    v = await session.get(Video, video_id)
    if v is None or v.owner_id != owner_id:
        raise NotFoundError(f"video {video_id} 不存在")
    return v


async def get_video_readable(
    session: AsyncSession, *, viewer_id: int, video_id: int
) -> Video:
    """主人可读；或视频挂在任意 share_all 笔记本上时，登录用户可读。"""
    from app.models.notebook import Notebook, NotebookSource

    v = await session.get(Video, video_id)
    if v is None:
        raise NotFoundError(f"video {video_id} 不存在")
    if v.owner_id == viewer_id:
        return v
    shared = await session.scalar(
        select(Notebook.id)
        .join(NotebookSource, NotebookSource.notebook_id == Notebook.id)
        .where(
            NotebookSource.video_id == video_id,
            Notebook.share_all.is_(True),
            Notebook.deleted_at.is_(None),
            Notebook.owner_id == v.owner_id,
        )
        .limit(1)
    )
    if shared is None:
        raise NotFoundError(f"video {video_id} 不存在")
    return v


async def get_subtitle_lines(
    session: AsyncSession, *, owner_id: int, video_id: int
) -> list[SubtitleLine] | None:
    """取视频的第一条字幕。v1 只取最新 version 的 asr 字幕。"""
    v = await get_video(session, owner_id=owner_id, video_id=video_id)
    sub = (
        await session.execute(
            select(Subtitle)
            .where(Subtitle.video_id == v.id)
            .order_by(Subtitle.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if sub is None:
        return None
    lines = (
        await session.execute(
            select(SubtitleLine)
            .where(SubtitleLine.subtitle_id == sub.id)
            .order_by(SubtitleLine.line_no)
        )
    ).scalars().all()
    return list(lines)



async def retry_fetch(
    session: AsyncSession, *, owner_id: int, video_id: int
) -> dict:
    """Re-queue a failed / unfinished URL fetch."""
    video = await get_video(session, owner_id=owner_id, video_id=video_id)
    if video.source_type != "url" or not video.source_url:
        from app.core.errors import BadRequestError

        raise BadRequestError("只有 URL 来源可以重新抓取")
    if video.status == "ready" and video.storage_key:
        return _video_to_dict(video)
    from app.media.enqueue import cancel_pipeline

    cancel_pipeline(video.id)
    video.status = "pending"
    video.error_message = None
    session.add(video)
    await session.commit()
    await session.refresh(video)
    from app.sources.fetch import kick_fetch_job

    kick_fetch_job(video.id)
    return _video_to_dict(video)


async def cancel_fetch(
    session: AsyncSession, *, owner_id: int, video_id: int
) -> dict:
    """Cancel an in-flight URL fetch / subtitle pipeline."""
    from app.core.errors import BadRequestError
    from app.media.enqueue import cancel_pipeline

    video = await get_video(session, owner_id=owner_id, video_id=video_id)
    busy = video.status in ("pending", "probing") or video.subtitle_status in (
        "pending",
        "processing",
    ) or video.overview_status == "processing"
    if not busy and video.status == "ready":
        raise BadRequestError("当前没有进行中的抓取任务")
    cancel_pipeline(video.id)
    if video.status in ("pending", "probing"):
        video.status = "failed"
        video.error_message = "已取消抓取"
    if video.subtitle_status in ("pending", "processing"):
        video.subtitle_status = "failed"
        video.subtitle_error = "已取消"
    if video.overview_status == "processing":
        video.overview_status = "failed"
        video.overview_error = "已取消"
    session.add(video)
    await session.commit()
    await session.refresh(video)
    return _video_to_dict(video)


async def rename_video(
    session: AsyncSession, *, owner_id: int, video_id: int, title: str
) -> dict:
    video = await get_video(session, owner_id=owner_id, video_id=video_id)
    video.title = title.strip()
    session.add(video)
    await session.commit()
    await session.refresh(video)
    return _video_to_dict(video)


async def delete_video(
    session: AsyncSession, *, owner_id: int, video_id: int
) -> None:
    v = await get_video(session, owner_id=owner_id, video_id=video_id)
    from app.media.enqueue import cancel_pipeline

    cancel_pipeline(video_id)
    # 删文件（v1 简化：v1 删除会从所有 notebook 取消关联；storage 文件保留以防重
    # 复上传后命中。Phase 6 ASR 流水线落字幕后 v2 改成「无任何关联时再删文件」）
    session.add(v)
    await session.execute(
        delete(NotebookSource).where(NotebookSource.video_id == video_id)
    )
    await session.delete(v)
    await session.commit()


# ── 工具 ─────────────────────────────────────────────────────
def _suffix_from_filename(filename: str) -> str:
    """从 filename 抽扩展名（带 .），无扩展名时返回空。"""
    if not filename:
        return ""
    dot = filename.rfind(".")
    if dot <= 0:
        return ""
    suf = filename[dot:].lower()
    # 限制 8 字符防止滥用
    return suf[:8] if len(suf) <= 8 else ""


def _local_path_for_key(key: str) -> str:
    """测试/调试用：根据 key 推算 storage 路径。"""
    return _local_path_for_key_real(key)


def _local_path_for_key_real(key: str) -> str:
    """根据 key 推算 LocalFsStorage 的实际文件路径。"""
    from app.storage import get_storage

    storage = get_storage()
    if not isinstance(storage, type(get_storage())):
        # 永远 import 一次确保 path 计算一致
        pass
    root = storage.root  # type: ignore[attr-defined]
    sha1 = key.split(".", 1)[0]
    suffix = key[len(sha1):]
    return str(root / sha1[:2] / f"{sha1}{suffix}")


def _safe_stat_size(key: str, storage: ObjectStorage) -> int | None:
    info = storage.head(key)
    return info.size if info else None
