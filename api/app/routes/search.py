"""/api/search — 跨平台视频聚合搜索。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import get_current_active_user
from app.models.user import User
from app.schemas.search import SearchRequest, SearchResponse
from app.search import run_search

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def post_search(
    body: SearchRequest,
    user: User = Depends(get_current_active_user),
) -> SearchResponse:
    _ = user
    return await run_search(body)
