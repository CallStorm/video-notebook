"""抓取网络：Cookie 规范化、运行时开关、admin API。"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.fetch_network.cookies_fs import normalize_cookie_text
from app.fetch_network.runtime import (
    invalidate_runtime_cache,
    resolve_for_platform,
    set_runtime_snapshot,
)
from app.models.user import User


async def _admin(db_session) -> str:
    u = User(phone="13800009991", name="admin", role="admin", status="active")
    u.set_password("adminpw1234")
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    token, _ = create_access_token(u.id, role="admin")
    return token


async def _user(db_session) -> str:
    u = User(phone="13800009992", name="user", role="user", status="active")
    u.set_password("userpw1234")
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    token, _ = create_access_token(u.id, role="user")
    return token


def test_normalize_header_cookies_to_netscape() -> None:
    text = normalize_cookie_text("bilibili", "SESSDATA=abc; bili_jct=xyz")
    assert "Netscape" in text
    assert "SESSDATA" in text
    assert ".bilibili.com" in text


def test_resolve_respects_cookie_and_proxy_toggles(tmp_path, monkeypatch) -> None:
    from app.core import config as config_mod
    from app.fetch_network import cookies_fs

    settings = config_mod.get_settings()
    monkeypatch.setattr(settings, "storage_root", tmp_path)
    invalidate_runtime_cache()

    cookies_fs.write_cookie_text("youtube", "# Netscape\n.youtube.com\tTRUE\t/\tFALSE\t0\tA\tb\n")
    set_runtime_snapshot(
        cookie_enabled={"youtube": True, "bilibili": False},
        proxy_enabled=True,
        proxy_url="http://127.0.0.1:7890",
        proxy_apply_to=["youtube"],
    )
    yt = resolve_for_platform("youtube")
    assert yt.cookiefile is not None
    assert yt.proxy == "http://127.0.0.1:7890"

    set_runtime_snapshot(
        cookie_enabled={"youtube": False, "bilibili": False},
        proxy_enabled=True,
        proxy_url="http://127.0.0.1:7890",
        proxy_apply_to=["youtube"],
    )
    yt2 = resolve_for_platform("youtube")
    assert yt2.cookiefile is None
    assert yt2.proxy == "http://127.0.0.1:7890"

    bili = resolve_for_platform("bilibili")
    assert bili.proxy is None
    invalidate_runtime_cache()


@pytest.mark.asyncio
async def test_admin_fetch_network_crud(client: AsyncClient, db_session, tmp_path, monkeypatch) -> None:
    from app.core import config as config_mod

    settings = config_mod.get_settings()
    monkeypatch.setattr(settings, "storage_root", tmp_path)
    invalidate_runtime_cache()

    token = await _admin(db_session)
    h = {"Authorization": f"Bearer {token}"}

    r = await client.get("/api/admin/fetch-network", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["cookies"]) == 2
    assert body["proxy"]["enabled"] is False
    assert "cookie_text" not in r.text.lower() or "SESSDATA" not in r.text

    r = await client.put(
        "/api/admin/fetch-network/cookies/youtube",
        headers=h,
        json={
            "enabled": True,
            "cookie_text": "# Netscape\n.youtube.com\tTRUE\t/\tFALSE\t0\tSID\tsecret-value\n",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["cookies"][0]["platform"] == "youtube"
    yt = next(c for c in r.json()["cookies"] if c["platform"] == "youtube")
    assert yt["enabled"] is True
    assert yt["cookie_set"] is True
    assert "secret-value" not in r.text

    r = await client.put(
        "/api/admin/fetch-network/proxy",
        headers=h,
        json={
            "enabled": True,
            "apply_to": ["youtube"],
            "scheme": "http",
            "host": "127.0.0.1",
            "port": 7890,
        },
    )
    assert r.status_code == 200, r.text
    proxy = r.json()["proxy"]
    assert proxy["enabled"] is True
    assert proxy["proxy_set"] is True
    assert proxy["apply_to"] == ["youtube"]
    assert proxy["scheme"] == "http"
    assert proxy["host"] == "127.0.0.1"
    assert proxy["port"] == 7890

    r = await client.delete("/api/admin/fetch-network/cookies/youtube", headers=h)
    assert r.status_code == 200
    yt = next(c for c in r.json()["cookies"] if c["platform"] == "youtube")
    assert yt["cookie_set"] is False
    assert yt["enabled"] is False


@pytest.mark.asyncio
async def test_fetch_network_requires_admin(client: AsyncClient, db_session) -> None:
    token = await _user(db_session)
    r = await client.get(
        "/api/admin/fetch-network",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
