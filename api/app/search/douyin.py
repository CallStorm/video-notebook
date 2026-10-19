"""Douyin video search — best-effort via Bing video results (MediaSync-style fallback)."""
from __future__ import annotations

import logging
import re
from urllib.parse import quote_plus, unquote

import httpx

from app.schemas.search import SearchResultItem

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
_VIDEO_ID_RE = re.compile(
    r"(?:www\.)?douyin\.com/video/(\d+)|(?:www\.)?iesdouyin\.com/share/video/(\d+)|v\.douyin\.com/([\w-]+)",
    re.I,
)


def search_douyin(query: str, *, limit: int) -> list[SearchResultItem]:
    """Search Douyin videos via Bing videos page, keeping only douyin links."""
    from app.fetch_network.runtime import resolve_for_platform

    q = f"site:douyin.com/video {query}"
    url = f"https://www.bing.com/videos/search?q={quote_plus(q)}&FORM=HDRSC3"
    headers = {
        "User-Agent": _UA,
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    net = resolve_for_platform("douyin")
    client_kwargs: dict = {"timeout": 25.0, "headers": headers, "follow_redirects": True}
    if net.proxy:
        client_kwargs["proxy"] = net.proxy
    try:
        with httpx.Client(**client_kwargs) as client:
            resp = client.get(url)
            resp.raise_for_status()
            html = resp.text
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"抖音搜索失败: {exc}") from exc

    items = _parse_bing_html(html, limit=limit)
    if not items:
        raise RuntimeError("抖音搜索无结果（平台风控或 Bing 未返回可解析链接）")
    return items


def _parse_bing_html(html: str, *, limit: int) -> list[SearchResultItem]:
    # Bing embeds media URLs in JSON-ish blobs and plain hrefs.
    candidates: list[str] = []
    for m in re.finditer(r"https?://(?:www\.)?(?:douyin|iesdouyin)\.com/[^\"'\\s<>]+", html, re.I):
        candidates.append(m.group(0).rstrip("\\\",')]}"))
    for m in re.finditer(r"https?://v\.douyin\.com/[\w-]+/?", html, re.I):
        candidates.append(m.group(0))

    seen: set[str] = set()
    items: list[SearchResultItem] = []
    for raw in candidates:
        cleaned = unquote(raw.replace("\\u0026", "&").replace("\\/", "/"))
        cleaned = cleaned.split("&amp;")[0].split("?")[0].rstrip("/")
        m = _VIDEO_ID_RE.search(cleaned)
        if not m:
            continue
        vid = next(g for g in m.groups() if g)
        if vid in seen:
            continue
        seen.add(vid)
        if cleaned.startswith("http") and "douyin.com" in cleaned:
            page_url = cleaned if "/video/" in cleaned or "v.douyin.com" in cleaned else (
                f"https://www.douyin.com/video/{vid}"
            )
        else:
            page_url = f"https://www.douyin.com/video/{vid}"

        title = _nearby_title(html, raw) or f"抖音视频 {vid}"
        items.append(
            SearchResultItem(
                id=vid,
                title=title[:500],
                url=page_url,
                thumbnail=None,
                platform="douyin",
                duration=None,
                uploader=None,
                uploader_url=None,
                view_count=None,
                description=None,
            )
        )
        if len(items) >= limit:
            break
    return items


def _nearby_title(html: str, url_fragment: str) -> str | None:
    idx = html.find(url_fragment[:80])
    if idx < 0:
        return None
    window = html[max(0, idx - 400) : idx + 200]
    for pat in (
        r'"title"\s*:\s*"([^"]{4,200})"',
        r"aria-label=\"([^\"]{4,200})\"",
        r"<a[^>]+title=\"([^\"]{4,200})\"",
    ):
        m = re.search(pat, window)
        if m:
            title = m.group(1).encode("utf-8").decode("unicode_escape", errors="ignore")
            title = re.sub(r"<[^>]+>", "", title).strip()
            if title and "http" not in title.lower():
                return title
    return None
