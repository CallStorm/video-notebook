"""Bilibili video search via official web API (fallback-friendly)."""
from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from app.schemas.search import SearchResultItem

logger = logging.getLogger(__name__)

_API = "https://api.bilibili.com/x/web-interface/search/type"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


def search_bilibili(query: str, *, limit: int) -> list[SearchResultItem]:
    from app.fetch_network.cookies_fs import cookie_header_from_file
    from app.fetch_network.runtime import resolve_for_platform

    params = {
        "search_type": "video",
        "keyword": query,
        "page": 1,
        "page_size": min(limit, 30),
    }
    headers = {
        "User-Agent": _UA,
        "Referer": "https://search.bilibili.com/",
        "Origin": "https://search.bilibili.com",
    }
    net = resolve_for_platform("bilibili")
    if net.cookiefile is not None:
        cookie = cookie_header_from_file("bilibili")
        if cookie:
            headers["Cookie"] = cookie
    client_kwargs: dict = {"timeout": 20.0, "headers": headers, "follow_redirects": True}
    if net.proxy:
        client_kwargs["proxy"] = net.proxy
    try:
        with httpx.Client(**client_kwargs) as client:
            resp = client.get(_API, params=params)
            resp.raise_for_status()
            payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"B站搜索失败: {exc}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("B站搜索返回无效响应")
    code = payload.get("code")
    if code not in (0, None):
        raise RuntimeError(f"B站搜索 API error: code={code} message={payload.get('message')}")

    data = payload.get("data") or {}
    results = data.get("result") or []
    items: list[SearchResultItem] = []
    for row in results:
        if not isinstance(row, dict):
            continue
        mapped = _map_row(row)
        if mapped is not None:
            items.append(mapped)
        if len(items) >= limit:
            break
    return items


def _map_row(row: dict[str, Any]) -> SearchResultItem | None:
    bvid = str(row.get("bvid") or "").strip()
    title = _strip_html(str(row.get("title") or ""))
    if not bvid or not title:
        return None
    url = f"https://www.bilibili.com/video/{bvid}"
    duration = _parse_duration(row.get("duration"))
    view_count = row.get("play")
    try:
        view_count = int(view_count) if view_count is not None else None
    except (TypeError, ValueError):
        view_count = None
    pic = row.get("pic")
    if isinstance(pic, str) and pic.startswith("//"):
        pic = "https:" + pic
    return SearchResultItem(
        id=bvid,
        title=title[:500],
        url=url,
        thumbnail=pic if isinstance(pic, str) else None,
        platform="bilibili",
        duration=duration,
        uploader=str(row.get("author") or "") or None,
        uploader_url=(
            f"https://space.bilibili.com/{row['mid']}" if row.get("mid") is not None else None
        ),
        view_count=view_count,
        description=_strip_html(str(row.get("description") or "")) or None,
    )


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).replace("&nbsp;", " ").strip()


def _parse_duration(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    parts = text.split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return None
    if len(nums) == 3:
        h, m, s = nums
        return h * 3600 + m * 60 + s
    if len(nums) == 2:
        m, s = nums
        return m * 60 + s
    if len(nums) == 1:
        return nums[0]
    return None
