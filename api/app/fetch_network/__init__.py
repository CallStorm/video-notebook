"""分平台 Cookie + 代理运行时。"""
from __future__ import annotations

from app.fetch_network.runtime import (
    apply_ytdlp_opts,
    detect_platform,
    resolve_for_platform,
    resolve_for_url,
)
from app.fetch_network.types import PlatformKey, ResolvedNetwork

__all__ = [
    "PlatformKey",
    "ResolvedNetwork",
    "apply_ytdlp_opts",
    "detect_platform",
    "resolve_for_platform",
    "resolve_for_url",
]
