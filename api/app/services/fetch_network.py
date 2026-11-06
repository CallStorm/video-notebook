"""Admin 抓取网络配置服务。"""
from __future__ import annotations

import time
from datetime import datetime
from urllib.parse import quote, urlparse

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError
from app.fetch_network.cookies_fs import (
    clear_cookie,
    cookie_exists,
    cookie_path,
    write_cookie_text,
)
from app.fetch_network.douyin import DouyinRuleError, normalize_host_rules
from app.fetch_network.runtime import invalidate_runtime_cache, set_runtime_snapshot
from app.fetch_network.types import PLATFORMS, PlatformKey
from app.models.fetch_network import FetchNetworkConfig
from app.schemas.fetch_network import (
    DouyinParserRead,
    DouyinParserTestResult,
    DouyinParserUpdate,
    FetchNetworkRead,
    PlatformCookieRead,
    PlatformCookieUpdate,
    ProxyRead,
    ProxyScheme,
    ProxyTestResult,
    ProxyUpdate,
)

_ROW_ID = 1


def _enabled_attr(platform: PlatformKey) -> str:
    return f"{platform}_cookie_enabled"


async def _ensure_row(session: AsyncSession) -> FetchNetworkConfig:
    row = await session.get(FetchNetworkConfig, _ROW_ID)
    if row is None:
        row = FetchNetworkConfig(
            id=_ROW_ID,
            youtube_cookie_enabled=False,
            bilibili_cookie_enabled=False,
            douyin_cookie_enabled=False,
            proxy_enabled=False,
            proxy_apply_to=[],
            douyin_parser_base_url="http://127.0.0.1:8001",
            douyin_host_rules=["v.douyin.com", "douyin.com", "iesdouyin.com"],
        )
        session.add(row)
        await session.flush()
    return row


def _publish_runtime(row: FetchNetworkConfig) -> None:
    set_runtime_snapshot(
        cookie_enabled={
            p: bool(getattr(row, f"{p}_cookie_enabled", False)) for p in PLATFORMS
        },
        proxy_enabled=bool(row.proxy_enabled),
        proxy_url=row.get_proxy_url() or None,
        proxy_apply_to=list(row.proxy_apply_to or []),
    )


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


async def get_fetch_network(session: AsyncSession) -> FetchNetworkRead:
    row = await _ensure_row(session)
    cookies: list[PlatformCookieRead] = []
    for platform in PLATFORMS:
        enabled = bool(getattr(row, _enabled_attr(platform)))
        path = cookie_path(platform)
        mtime = None
        if path.is_file():
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
        cookies.append(
            PlatformCookieRead(
                platform=platform,
                enabled=enabled,
                cookie_set=cookie_exists(platform),
                updated_at=_iso(mtime),
            )
        )
    apply = [p for p in (row.proxy_apply_to or []) if p in PLATFORMS]
    _publish_runtime(row)
    scheme, host, port = _parse_proxy_parts(row.get_proxy_url())
    return FetchNetworkRead(
        cookies=cookies,
        proxy=ProxyRead(
            enabled=bool(row.proxy_enabled),
            proxy_set=bool(row.get_proxy_url()),
            apply_to=apply,  # type: ignore[arg-type]
            scheme=scheme,
            host=host,
            port=port,
        ),
        douyin_parser=_douyin_parser_read(row),
    )


def _parse_proxy_parts(url: str) -> tuple[ProxyScheme | None, str | None, int | None]:
    text = (url or "").strip()
    if not text:
        return None, None, None
    parsed = urlparse(text)
    scheme_raw = (parsed.scheme or "").lower()
    scheme: ProxyScheme | None = None
    if scheme_raw in ("http", "https", "socks5", "socks4"):
        scheme = scheme_raw  # type: ignore[assignment]
    host = parsed.hostname
    port = parsed.port
    return scheme, host, port


def _compose_proxy_url(body: ProxyUpdate) -> str:
    host = body.host.strip()
    if not host:
        raise BadRequestError("代理地址不能为空")
    user = (body.username or "").strip()
    password = (body.password or "").strip()
    auth = ""
    if user or password:
        auth = f"{quote(user, safe='')}:{quote(password, safe='')}@"
    return f"{body.scheme}://{auth}{host}:{body.port}"


async def update_platform_cookie(
    session: AsyncSession, platform: PlatformKey, body: PlatformCookieUpdate
) -> FetchNetworkRead:
    row = await _ensure_row(session)
    setattr(row, _enabled_attr(platform), bool(body.enabled))
    text = body.cookie_text
    if text is not None and text.strip():
        try:
            write_cookie_text(platform, text)
        except ValueError as exc:
            raise BadRequestError(str(exc)) from exc
    await session.commit()
    await session.refresh(row)
    invalidate_runtime_cache()
    _publish_runtime(row)
    return await get_fetch_network(session)


async def delete_platform_cookie(
    session: AsyncSession, platform: PlatformKey
) -> FetchNetworkRead:
    row = await _ensure_row(session)
    clear_cookie(platform)
    setattr(row, _enabled_attr(platform), False)
    await session.commit()
    await session.refresh(row)
    invalidate_runtime_cache()
    _publish_runtime(row)
    return await get_fetch_network(session)


async def update_proxy(session: AsyncSession, body: ProxyUpdate) -> FetchNetworkRead:
    row = await _ensure_row(session)
    row.proxy_enabled = bool(body.enabled)
    apply = [p for p in body.apply_to if p in PLATFORMS]
    row.proxy_apply_to = apply
    row.set_proxy_url(_compose_proxy_url(body))
    await session.commit()
    await session.refresh(row)
    invalidate_runtime_cache()
    _publish_runtime(row)
    return await get_fetch_network(session)


async def clear_proxy(session: AsyncSession) -> FetchNetworkRead:
    row = await _ensure_row(session)
    row.proxy_enabled = False
    row.proxy_apply_to = []
    row.set_proxy_url(None)
    await session.commit()
    await session.refresh(row)
    invalidate_runtime_cache()
    _publish_runtime(row)
    return await get_fetch_network(session)


def _douyin_parser_read(row: FetchNetworkConfig) -> DouyinParserRead:
    rules = [str(item) for item in (row.douyin_host_rules or []) if str(item).strip()]
    base = (row.douyin_parser_base_url or "").strip() or "http://127.0.0.1:8001"
    return DouyinParserRead(
        base_url=base,
        api_key_set=bool(row.get_douyin_parser_api_key().strip()),
        host_rules=rules,
    )


def _clean_parser_base_url(raw: str) -> str:
    text = raw.strip().rstrip("/")
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise BadRequestError("解析服务地址需要是 http 或 https 链接")
    return text


async def update_douyin_parser(
    session: AsyncSession, body: DouyinParserUpdate
) -> FetchNetworkRead:
    row = await _ensure_row(session)
    row.douyin_parser_base_url = _clean_parser_base_url(body.base_url)
    try:
        row.douyin_host_rules = normalize_host_rules(body.host_rules)
    except DouyinRuleError as exc:
        raise BadRequestError(str(exc)) from exc
    if body.api_key is not None and body.api_key.strip():
        row.set_douyin_parser_api_key(body.api_key)
    await session.commit()
    await session.refresh(row)
    invalidate_runtime_cache()
    _publish_runtime(row)
    return await get_fetch_network(session)


async def test_douyin_parser(session: AsyncSession) -> DouyinParserTestResult:
    row = await _ensure_row(session)
    base = (row.douyin_parser_base_url or "").strip().rstrip("/")
    key = row.get_douyin_parser_api_key().strip()
    if not base or not key:
        return DouyinParserTestResult(ok=False, message="请先保存地址和 API Key", latency_ms=None)
    started = time.perf_counter()
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.get(
                f"{base}/api/v1/system/status",
                headers={"X-API-Key": key, "Accept": "application/json"},
            )
        latency = int((time.perf_counter() - started) * 1000)
        if resp.status_code in {401, 403}:
            return DouyinParserTestResult(ok=False, message="API Key 无效", latency_ms=latency)
        if resp.status_code >= 400:
            return DouyinParserTestResult(
                ok=False,
                message=f"解析服务返回 HTTP {resp.status_code}",
                latency_ms=latency,
            )
        body = resp.json()
        if isinstance(body, dict) and body.get("success") is False:
            error = body.get("error") if isinstance(body.get("error"), dict) else {}
            message = str(error.get("message") or "解析服务拒绝了这次测试")
            return DouyinParserTestResult(ok=False, message=message, latency_ms=latency)
        return DouyinParserTestResult(ok=True, message="解析服务可访问", latency_ms=latency)
    except Exception as exc:  # noqa: BLE001
        latency = int((time.perf_counter() - started) * 1000)
        return DouyinParserTestResult(
            ok=False,
            message=str(exc) or "无法连接解析服务",
            latency_ms=latency,
        )


async def test_proxy(session: AsyncSession) -> ProxyTestResult:
    row = await _ensure_row(session)
    url = row.get_proxy_url().strip()
    if not url:
        return ProxyTestResult(ok=False, message="未配置代理 URL", latency_ms=None)
    started = time.perf_counter()
    try:
        with httpx.Client(proxy=url, timeout=15.0, follow_redirects=True) as client:
            resp = client.get("https://www.youtube.com", headers={"User-Agent": "video-notebook/1.0"})
            latency = int((time.perf_counter() - started) * 1000)
            if resp.status_code >= 400:
                return ProxyTestResult(
                    ok=False,
                    message=f"代理可达但目标返回 HTTP {resp.status_code}",
                    latency_ms=latency,
                )
            return ProxyTestResult(ok=True, message="代理可用（已探测 youtube.com）", latency_ms=latency)
    except Exception as exc:  # noqa: BLE001
        latency = int((time.perf_counter() - started) * 1000)
        return ProxyTestResult(ok=False, message=str(exc) or "代理测试失败", latency_ms=latency)
