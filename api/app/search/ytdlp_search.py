"""yt-dlp flat search helpers (YouTube / Bilibili)."""
from __future__ import annotations

import logging
from typing import Any

from app.schemas.search import Platform, SearchResultItem

logger = logging.getLogger(__name__)


def search_with_ytdlp(query_spec: str, *, platform: Platform, limit: int) -> list[SearchResultItem]:
    """Run a yt-dlp search URL like ``ytsearch12:foo`` / ``bilisearch12:foo``."""
    import yt_dlp

    from app.fetch_network.runtime import apply_ytdlp_opts

    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "skip_download": True,
        "playlistend": limit,
        "ignoreerrors": True,
        "socket_timeout": 20,
    }
    opts = apply_ytdlp_opts(opts, platform=platform)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(query_spec, download=False)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"{platform} 搜索失败: {_clean(exc)}") from exc

    if not info:
        return []
    entries = info.get("entries") or []
    items: list[SearchResultItem] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        mapped = _map_entry(entry, platform=platform)
        if mapped is not None:
            items.append(mapped)
        if len(items) >= limit:
            break
    return items


def _map_entry(entry: dict[str, Any], *, platform: Platform) -> SearchResultItem | None:
    url = (entry.get("url") or entry.get("webpage_url") or "").strip()
    video_id = str(entry.get("id") or "").strip()
    title = (entry.get("title") or "").strip()
    if not title:
        return None

    if platform == "youtube":
        if not video_id and "watch?v=" in url:
            video_id = url.split("watch?v=", 1)[1].split("&", 1)[0]
        if not video_id:
            return None
        if not url or not url.startswith("http"):
            url = f"https://www.youtube.com/watch?v={video_id}"
        thumb = entry.get("thumbnail") or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    elif platform == "bilibili":
        if not url or not url.startswith("http"):
            bvid = video_id if video_id.startswith("BV") else None
            if not bvid:
                return None
            url = f"https://www.bilibili.com/video/{bvid}"
            video_id = bvid
        elif not video_id:
            video_id = _bvid_from_url(url) or url
        thumb = entry.get("thumbnail")
    else:
        if not url:
            return None
        if not video_id:
            video_id = url
        thumb = entry.get("thumbnail")

    duration = entry.get("duration")
    if duration is not None:
        try:
            duration = int(float(duration))
        except (TypeError, ValueError):
            duration = None

    view_count = entry.get("view_count")
    if view_count is not None:
        try:
            view_count = int(view_count)
        except (TypeError, ValueError):
            view_count = None

    return SearchResultItem(
        id=video_id,
        title=title[:500],
        url=url,
        thumbnail=thumb,
        platform=platform,
        duration=duration,
        uploader=(entry.get("uploader") or entry.get("channel") or None),
        uploader_url=entry.get("uploader_url") or entry.get("channel_url"),
        view_count=view_count,
        description=(entry.get("description") or None),
    )


def _bvid_from_url(url: str) -> str | None:
    import re

    m = re.search(r"(BV[\w]+)", url)
    return m.group(1) if m else None


def _clean(exc: BaseException) -> str:
    return str(exc).strip() or exc.__class__.__name__
