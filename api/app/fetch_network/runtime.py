"""同步解析 Cookie/代理，供 yt-dlp / httpx 使用。"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from app.fetch_network.cookies_fs import cookie_exists, cookie_path
from app.fetch_network.types import PLATFORMS, PlatformKey, ResolvedNetwork

logger = logging.getLogger(__name__)


@dataclass
class _Snapshot:
    cookie_enabled: dict[PlatformKey, bool]
    proxy_enabled: bool
    proxy_url: str | None
    proxy_apply_to: set[PlatformKey]


_snapshot: _Snapshot | None = None


def invalidate_runtime_cache() -> None:
    global _snapshot
    _snapshot = None


def set_runtime_snapshot(
    *,
    cookie_enabled: dict[PlatformKey, bool],
    proxy_enabled: bool,
    proxy_url: str | None,
    proxy_apply_to: list[str],
) -> None:
    global _snapshot
    apply: set[PlatformKey] = set()
    for p in proxy_apply_to:
        if p in PLATFORMS:
            apply.add(p)  # type: ignore[arg-type]
    _snapshot = _Snapshot(
        cookie_enabled={p: bool(cookie_enabled.get(p, False)) for p in PLATFORMS},
        proxy_enabled=bool(proxy_enabled),
        proxy_url=(proxy_url or "").strip() or None,
        proxy_apply_to=apply,
    )


def _load_snapshot() -> _Snapshot:
    global _snapshot
    if _snapshot is not None:
        return _snapshot
    # 冷启动：同步读 DB；失败则空配置
    try:
        snap = _load_snapshot_from_db()
    except Exception as exc:  # noqa: BLE001
        logger.warning("load fetch_network config failed: %s", exc)
        snap = _Snapshot(
            cookie_enabled={p: False for p in PLATFORMS},
            proxy_enabled=False,
            proxy_url=None,
            proxy_apply_to=set(),
        )
    _snapshot = snap
    return snap


def _load_snapshot_from_db() -> _Snapshot:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.core.config import get_settings
    from app.models.fetch_network import FetchNetworkConfig

    engine = create_engine(get_settings().database_sync_url, pool_pre_ping=True)
    try:
        with Session(engine) as session:
            row = session.get(FetchNetworkConfig, 1)
            if row is None:
                return _Snapshot(
                    cookie_enabled={p: False for p in PLATFORMS},
                    proxy_enabled=False,
                    proxy_url=None,
                    proxy_apply_to=set(),
                )
            apply_raw = row.proxy_apply_to or []
            apply: set[PlatformKey] = set()
            for p in apply_raw:
                if p in PLATFORMS:
                    apply.add(p)  # type: ignore[arg-type]
            return _Snapshot(
                cookie_enabled={
                    "youtube": bool(row.youtube_cookie_enabled),
                    "bilibili": bool(row.bilibili_cookie_enabled),
                    "douyin": bool(row.douyin_cookie_enabled),
                },
                proxy_enabled=bool(row.proxy_enabled),
                proxy_url=row.get_proxy_url().strip() or None,
                proxy_apply_to=apply,
            )
    finally:
        engine.dispose()


def detect_platform(url: str) -> PlatformKey | None:
    host = (urlparse(url).hostname or "").lower()
    if host.endswith("youtube.com") or host == "youtu.be" or host.endswith(".youtu.be"):
        return "youtube"
    if (
        host.endswith("bilibili.com")
        or host.endswith("b23.tv")
        or host == "b23.tv"
        or host.endswith("bilivideo.com")
    ):
        return "bilibili"
    if (
        host.endswith("douyin.com")
        or host.endswith("iesdouyin.com")
        or host.endswith("douyinpic.com")
        or host.endswith("douyinvod.com")
    ):
        return "douyin"
    return None


def resolve_for_platform(platform: PlatformKey) -> ResolvedNetwork:
    snap = _load_snapshot()
    cookiefile: Path | None = None
    if snap.cookie_enabled.get(platform) and cookie_exists(platform):
        cookiefile = cookie_path(platform)
    proxy: str | None = None
    if snap.proxy_enabled and snap.proxy_url and platform in snap.proxy_apply_to:
        proxy = snap.proxy_url
    return ResolvedNetwork(platform=platform, cookiefile=cookiefile, proxy=proxy)


def resolve_for_url(url: str) -> ResolvedNetwork:
    platform = detect_platform(url)
    if platform is None:
        # 未知站：不带平台 cookie，也不猜代理
        return ResolvedNetwork(platform=None, cookiefile=None, proxy=None)
    return resolve_for_platform(platform)


def apply_ytdlp_opts(opts: dict, *, url: str | None = None, platform: PlatformKey | None = None) -> dict:
    """Mutate/copy yt-dlp opts with cookiefile + proxy from admin config."""
    if platform is None and url:
        resolved = resolve_for_url(url)
    elif platform is not None:
        resolved = resolve_for_platform(platform)
    else:
        return opts
    out = dict(opts)
    if resolved.cookiefile is not None:
        out["cookiefile"] = str(resolved.cookiefile)
    if resolved.proxy:
        out["proxy"] = resolved.proxy
    return out
