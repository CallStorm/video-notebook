"""把相对存储地址补成 Agent 可直接打开的绝对 URL。"""
from __future__ import annotations

from fastapi import Request

from app.core.config import get_settings


def public_origin(request: Request) -> str:
    configured = (get_settings().public_base_url or "").strip().rstrip("/")
    if configured:
        return configured
    forwarded = (request.headers.get("x-forwarded-host") or "").split(",")[0].strip()
    if forwarded:
        proto = (request.headers.get("x-forwarded-proto") or request.url.scheme).split(",")[0].strip()
        return f"{proto}://{forwarded}"
    return str(request.base_url).rstrip("/")


def absolute_url(origin: str, url: str | None) -> str | None:
    if not url:
        return url
    if url.startswith("/"):
        return origin.rstrip("/") + url
    return url


def connect_info(origin: str, plaintext: str | None = None) -> dict[str, str]:
    base = origin.rstrip("/")
    token = plaintext or "<TOKEN>"
    return {
        "mcp_url": f"{base}/mcp",
        "skill_url": f"{base}/agent/skill.md",
        "llms_url": f"{base}/llms.txt",
        "openapi_url": f"{base}/agent/openapi.json",
        "install_url": f"{base}/agent/install.sh",
        "install_command": f"curl -fsSL {base}/agent/install.sh | sh -s -- --token {token}",
    }
