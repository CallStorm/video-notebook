"""Bilibili video search via official web API (fallback-friendly)."""
from __future__ import annotations

import logging
import random
import re
import time
import uuid
from typing import Any

import httpx

from app.schemas.search import SearchResultItem

logger = logging.getLogger(__name__)

_API = "https://api.bilibili.com/x/web-interface/search/type"
_NAV = "https://api.bilibili.com/x/web-interface/nav"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
# B站对无 buvid / 短时高频请求常回 HTTP 412 HTML；多试几次并带访客 cookie
_MAX_ATTEMPTS = 3


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
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    net = resolve_for_platform("bilibili")
    configured_cookie = None
    if net.cookiefile is not None:
        configured_cookie = cookie_header_from_file("bilibili")

    client_kwargs: dict = {
        "timeout": 20.0,
        "headers": headers,
        "follow_redirects": True,
    }
    if net.proxy:
        client_kwargs["proxy"] = net.proxy

    last_exc: Exception | None = None
    with httpx.Client(**client_kwargs) as client:
        # 先种访客 buvid；若后台配了 Cookie 再叠加（同名以后台为准）
        _seed_guest_cookies(client)
        if configured_cookie:
            client.cookies.update(_parse_cookie_header(configured_cookie))
        # 轻量暖机：拿一次 nav，让 Set-Cookie / 风控状态落进 jar
        _warmup(client)

        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                resp = client.get(_API, params=params)
                if resp.status_code == 412:
                    raise RuntimeError(
                        f"B站搜索被风控 (HTTP 412)，第 {attempt}/{_MAX_ATTEMPTS} 次"
                    )
                resp.raise_for_status()
                try:
                    payload = resp.json()
                except Exception as exc:  # noqa: BLE001
                    raise RuntimeError(
                        f"B站搜索返回非 JSON（HTTP {resp.status_code}）"
                    ) from exc

                if not isinstance(payload, dict):
                    raise RuntimeError("B站搜索返回无效响应")
                code = payload.get("code")
                if code not in (0, None):
                    raise RuntimeError(
                        f"B站搜索 API error: code={code} message={payload.get('message')}"
                    )

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
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.info("bilibili search attempt %s failed: %s", attempt, exc)
                if attempt >= _MAX_ATTEMPTS:
                    break
                # 换一套访客 buvid 再试，避免连续 412
                _seed_guest_cookies(client, force_new=True)
                time.sleep(0.35 + random.random() * 0.4)

    raise RuntimeError(f"B站搜索失败: {last_exc}") from last_exc


def _seed_guest_cookies(client: httpx.Client, *, force_new: bool = False) -> None:
    """无登录也可搜：B站常用 buvid3 / b_nut 识别访客。"""
    if force_new or "buvid3" not in client.cookies:
        client.cookies.set("buvid3", f"{uuid.uuid4()}infoc", domain=".bilibili.com", path="/")
    if force_new or "b_nut" not in client.cookies:
        client.cookies.set("b_nut", str(int(time.time())), domain=".bilibili.com", path="/")
    if force_new or "buvid4" not in client.cookies:
        # buvid4 非必须；给一个占位降低偶发 412
        client.cookies.set(
            "buvid4",
            f"{uuid.uuid4().hex}%2C{int(time.time())}",
            domain=".bilibili.com",
            path="/",
        )


def _warmup(client: httpx.Client) -> None:
    try:
        client.get(_NAV, timeout=8.0)
    except Exception as exc:  # noqa: BLE001
        logger.debug("bilibili nav warmup skipped: %s", exc)


def _parse_cookie_header(header: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in header.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        name, value = name.strip(), value.strip()
        if name:
            out[name] = value
    return out


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
