"""/api/notebooks/{id}/sources/* 与 /api/sources/* — 上传 / URL fetch / 查询 / 删除。

- upload：multipart，落 LocalFsStorage，ffprobe 探查后 kick 字幕流水线
- fetch_url：创建 pending 记录后 kick yt-dlp 后台抓取（probing → ready/failed）
- 字幕：内嵌 / 平台 / ASR 链
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.notebook import FetchUrlRequest, SubtitleView, VideoRead, VideoRename
from app.services import sources as svc
from app.storage import get_storage

router = APIRouter(tags=["sources"])


@router.post(
    "/notebooks/{notebook_id}/sources/upload",
    response_model=VideoRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_upload(
    notebook_id: int,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    """multipart/form-data 上传一个视频文件。"""
    if not file.filename:
        from app.core.errors import BadRequestError

        raise BadRequestError("缺少 filename")
    # 一次性读入（v1 不分块；如需流式后续扩展）
    data = await file.read()
    if not data:
        from app.core.errors import BadRequestError

        raise BadRequestError("空文件")
    # 写存储
    storage = get_storage()
    suffix = _suffix(file.filename)
    storage.put(data=data, content_type=file.content_type, suffix=suffix)
    # 入库 + 关联 + 异步探查
    from io import BytesIO

    created = await svc.upload_video(
        session,
        owner_id=user.id,
        notebook_id=notebook_id,
        filename=file.filename,
        content_type=file.content_type,
        stream=BytesIO(data),
    )
    from app.subtitles.pipeline import kick_subtitle_job

    kick_subtitle_job(created["id"], notebook_id=notebook_id)
    return created


@router.post(
    "/notebooks/{notebook_id}/sources/fetch",
    response_model=VideoRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_fetch_url(
    notebook_id: int,
    body: FetchUrlRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    """粘贴视频 URL 入库并后台抓取。"""
    return await svc.fetch_url(
        session, owner_id=user.id, notebook_id=notebook_id, url=body.url
    )


@router.get("/sources/{video_id}", response_model=VideoRead)
async def get_video(
    video_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    v = await svc.get_video(session, owner_id=user.id, video_id=video_id)
    return svc._video_to_dict(v)  # type: ignore[attr-defined]


@router.post("/sources/{video_id}/retry-fetch", response_model=VideoRead)
async def retry_fetch_url(
    video_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    """重新抓取失败的 URL 来源。"""
    return await svc.retry_fetch(session, owner_id=user.id, video_id=video_id)


@router.post("/sources/{video_id}/cancel-fetch", response_model=VideoRead)
async def cancel_fetch_url(
    video_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    """取消进行中的抓取 / 字幕任务。"""
    return await svc.cancel_fetch(session, owner_id=user.id, video_id=video_id)


@router.patch("/sources/{video_id}", response_model=VideoRead)
async def rename_video(
    video_id: int,
    body: VideoRename,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    return await svc.rename_video(
        session, owner_id=user.id, video_id=video_id, title=body.title
    )


@router.delete("/sources/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video(
    video_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    await svc.delete_video(session, owner_id=user.id, video_id=video_id)
    return None


@router.get("/sources/{video_id}/play_url")
async def get_play_url(
    video_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    """v1 签发内部代理 URL（前端 /api/storage/{key}?token=...）。"""
    v = await svc.get_video_readable(session, viewer_id=user.id, video_id=video_id)
    if not v.storage_key:
        from app.core.errors import NotFoundError

        raise NotFoundError("视频尚未完成存储")
    storage = get_storage()
    url = storage.signed_url(v.storage_key)
    return {"url": url, "expires_in": 3600}


@router.get("/sources/{video_id}/subtitle", response_model=SubtitleView)
async def get_subtitle(
    video_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    from app.subtitles.pipeline import read_subtitle_for_viewer

    return await read_subtitle_for_viewer(
        session, viewer_id=user.id, video_id=video_id
    )


@router.post(
    "/sources/{video_id}/subtitle/regenerate",
    response_model=SubtitleView,
    status_code=status.HTTP_202_ACCEPTED,
)
async def regenerate_subtitle(
    video_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    """重新转写。生成过程中仍可读上一版字幕。"""
    from app.subtitles.pipeline import request_regenerate

    return await request_regenerate(session, owner_id=user.id, video_id=video_id)


def _suffix(filename: str) -> str:
    if not filename:
        return ""
    dot = filename.rfind(".")
    if dot <= 0:
        return ""
    suf = filename[dot:].lower()
    return suf[:8] if len(suf) <= 8 else ""
