"""抓取与网络：Cookie / 代理 admin schema。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Platform = Literal["youtube", "bilibili", "douyin"]
PLATFORMS: tuple[Platform, ...] = ("youtube", "bilibili", "douyin")


class PlatformCookieRead(BaseModel):
    platform: Platform
    enabled: bool
    cookie_set: bool
    updated_at: str | None = None


ProxyScheme = Literal["http", "https", "socks5", "socks4"]


class ProxyRead(BaseModel):
    enabled: bool
    proxy_set: bool
    apply_to: list[Platform] = []
    scheme: ProxyScheme | None = None
    host: str | None = None
    port: int | None = None


class FetchNetworkRead(BaseModel):
    cookies: list[PlatformCookieRead]
    proxy: ProxyRead


class PlatformCookieUpdate(BaseModel):
    enabled: bool
    # 空字符串 / null = 不修改已有 cookie 正文；有内容则覆盖写入
    cookie_text: str | None = None


class ProxyUpdate(BaseModel):
    enabled: bool
    apply_to: list[Platform] = Field(default_factory=list)
    scheme: ProxyScheme = "http"
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    # 可选认证；都空则不带 userinfo
    username: str | None = None
    password: str | None = None


class ProxyTestResult(BaseModel):
    ok: bool
    message: str
    latency_ms: int | None = None
