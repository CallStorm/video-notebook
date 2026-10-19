"""Aggregate video search across YouTube / Bilibili / Douyin."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from app.schemas.search import (
    ALL_PLATFORMS,
    Platform,
    PlatformSearchError,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)
from app.search.bilibili import search_bilibili
from app.search.douyin import search_douyin
from app.search.ytdlp_search import search_with_ytdlp

logger = logging.getLogger(__name__)


async def run_search(body: SearchRequest) -> SearchResponse:
    platforms = body.platforms or list(ALL_PLATFORMS)
    # de-dupe while preserving order
    seen: set[Platform] = set()
    ordered: list[Platform] = []
    for p in platforms:
        if p not in seen:
            seen.add(p)
            ordered.append(p)

    limit = body.limit_per_platform
    query = body.query.strip()

    tasks = [asyncio.create_task(_search_one(p, query, limit)) for p in ordered]
    settled = await asyncio.gather(*tasks)

    items: list[SearchResultItem] = []
    errors: list[PlatformSearchError] = []
    for platform, result in zip(ordered, settled, strict=True):
        if isinstance(result, PlatformSearchError):
            errors.append(result)
        else:
            items.extend(result)
    return SearchResponse(items=items, errors=errors)


async def _search_one(
    platform: Platform, query: str, limit: int
) -> list[SearchResultItem] | PlatformSearchError:
    fn = _DISPATCH[platform]
    try:
        return await asyncio.to_thread(fn, query, limit)
    except Exception as exc:  # noqa: BLE001
        logger.warning("search failed platform=%s: %s", platform, exc)
        return PlatformSearchError(platform=platform, message=str(exc) or "搜索失败")


def _youtube(query: str, limit: int) -> list[SearchResultItem]:
    return search_with_ytdlp(f"ytsearch{limit}:{query}", platform="youtube", limit=limit)


def _bilibili(query: str, limit: int) -> list[SearchResultItem]:
    try:
        return search_bilibili(query, limit=limit)
    except Exception as api_exc:  # noqa: BLE001
        logger.info("bilibili API search failed, fallback yt-dlp: %s", api_exc)
        return search_with_ytdlp(
            f"bilisearch{limit}:{query}", platform="bilibili", limit=limit
        )


def _douyin(query: str, limit: int) -> list[SearchResultItem]:
    return search_douyin(query, limit=limit)


_DISPATCH: dict[Platform, Callable[[str, int], list[SearchResultItem]]] = {
    "youtube": _youtube,
    "bilibili": _bilibili,
    "douyin": _douyin,
}
