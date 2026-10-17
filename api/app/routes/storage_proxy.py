"""/api/storage/{key} — 视频代理（用 LocalFsStorage 的 signed token 校验后流式回写）。"""
from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from app.core.errors import NotFoundError, UnauthorizedError
from app.storage import get_storage

router = APIRouter(prefix="/storage", tags=["storage"])


@router.get("/{key:path}")
async def stream_storage(
    key: str,
    token: str | None = Query(default=None),
):
    storage = get_storage()
    if not token:
        raise UnauthorizedError("Missing signed token")
    if not storage.verify_signed_token(key, token, max_age_seconds=3600):
        raise UnauthorizedError("token 无效或已过期")
    try:
        info = storage.head(key)
        path = storage.local_path(key)
    except ValueError as exc:
        raise UnauthorizedError("token 无效或已过期") from exc
    if info is None:
        raise NotFoundError(f"object {key} 不存在")
    content_type = info.content_type if info else None
    if not content_type:
        if key.endswith(".mp4"):
            content_type = "video/mp4"
        elif key.endswith(".webm"):
            content_type = "video/webm"
        elif key.endswith(".mov"):
            content_type = "video/quicktime"
        else:
            content_type = "application/octet-stream"

    # FileResponse 自带 Range，浏览器才能拖动播放。
    return FileResponse(path, media_type=content_type)
