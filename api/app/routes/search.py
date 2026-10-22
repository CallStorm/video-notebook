"""/api/search — 跨平台视频聚合搜索 + 页内预览流。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from app.core.deps import get_current_active_user
from app.models.user import User
from app.schemas.search import SearchRequest, SearchResponse
from app.search import run_search
from app.search.preview import get_preview, iter_preview_bytes, resolve_preview

router = APIRouter(tags=["search"])


class PreviewRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)

    @field_validator("url")
    @classmethod
    def _strip(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.startswith(("http://", "https://")):
            raise ValueError("url 必须是 http(s) 链接")
        return cleaned


class PreviewResponse(BaseModel):
    token: str
    play_url: str
    expires_in: int = 600
    title: str | None = None


@router.post("/search", response_model=SearchResponse)
async def post_search(
    body: SearchRequest,
    user: User = Depends(get_current_active_user),
) -> SearchResponse:
    _ = user
    return await run_search(body)


@router.post("/search/preview", response_model=PreviewResponse)
async def post_search_preview(
    body: PreviewRequest,
    user: User = Depends(get_current_active_user),
) -> PreviewResponse:
    """解析平台直链并签发短时预览 token（类 MediaSync resolve_preview）。"""
    _ = user
    token, entry = resolve_preview(body.url)
    return PreviewResponse(
        token=token,
        play_url=f"/api/search/preview/stream/{token}",
        expires_in=600,
        title=entry.title,
    )


@router.get("/search/preview/stream/{token}")
async def get_search_preview_stream(token: str):
    """代理预览媒体流；token 即凭证，供 <video src> 使用。"""
    from starlette.concurrency import iterate_in_threadpool

    entry = get_preview(token)
    return StreamingResponse(
        iterate_in_threadpool(iter_preview_bytes(entry)),
        media_type="video/mp4",
        headers={
            "Cache-Control": "no-cache, no-store",
            "Accept-Ranges": "none",
        },
    )
