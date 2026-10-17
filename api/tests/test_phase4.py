"""Phase 4：Notebook + Source 端到端。"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.user import User

pytestmark = pytest.mark.asyncio


async def _user(db_session, phone="13800000777", role="user") -> tuple[User, str]:
    u = User(phone=phone, name=phone, role=role, status="active")
    u.set_password("userpw1234")
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    token, _ = create_access_token(u.id, role=role)
    return u, token


# ── Notebook ──────────────────────────────────────────────


async def test_create_list_get_update_delete_notebook(client: AsyncClient, db_session):
    u, token = await _user(db_session)
    h = {"Authorization": f"Bearer {token}"}

    # create
    r = await client.post(
        "/api/notebooks",
        headers=h,
        json={"title": "我的第一个笔记本", "icon": "🎬"},
    )
    assert r.status_code == 201, r.text
    nb = r.json()
    assert nb["title"] == "我的第一个笔记本"
    assert nb["icon"] == "🎬"
    assert nb["is_pinned"] is False
    assert nb["share_all"] is False
    assert nb["source_count"] == 0
    nb_id = nb["id"]

    # list
    r = await client.get("/api/notebooks", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == nb_id

    # get detail
    r = await client.get(f"/api/notebooks/{nb_id}", headers=h)
    assert r.status_code == 200
    detail = r.json()
    assert detail["id"] == nb_id
    assert detail["sources"] == []

    # update
    r = await client.patch(
        f"/api/notebooks/{nb_id}", headers=h, json={"is_pinned": True}
    )
    assert r.status_code == 200
    assert r.json()["is_pinned"] is True

    # share_all
    r = await client.post(f"/api/notebooks/{nb_id}/share_all", headers=h)
    assert r.status_code == 200
    assert r.json()["share_all"] is True
    r = await client.delete(f"/api/notebooks/{nb_id}/share_all", headers=h)
    assert r.status_code == 200
    assert r.json()["share_all"] is False

    # search
    r = await client.get("/api/notebooks?search=不存", headers=h)
    assert r.json()["total"] == 0
    r = await client.get("/api/notebooks?search=第一", headers=h)
    assert r.json()["total"] == 1

    # delete (soft)
    r = await client.delete(f"/api/notebooks/{nb_id}", headers=h)
    assert r.status_code == 204
    r = await client.get(f"/api/notebooks/{nb_id}", headers=h)
    assert r.status_code == 404
    r = await client.get("/api/notebooks", headers=h)
    assert r.json()["total"] == 0


async def test_notebook_owner_isolation(client: AsyncClient, db_session):
    u1, t1 = await _user(db_session, phone="13800000771")
    u2, t2 = await _user(db_session, phone="13800000772")

    r = await client.post(
        "/api/notebooks",
        headers={"Authorization": f"Bearer {t1}"},
        json={"title": "u1's"},
    )
    assert r.status_code == 201
    nb_id = r.json()["id"]

    # u2 不应看到 u1 的 notebook
    r = await client.get(
        f"/api/notebooks/{nb_id}",
        headers={"Authorization": f"Bearer {t2}"},
    )
    assert r.status_code == 404
    r = await client.get(
        "/api/notebooks",
        headers={"Authorization": f"Bearer {t2}"},
    )
    assert r.json()["total"] == 0


# ── Sources ──────────────────────────────────────────────


async def test_upload_then_fetch_url_then_list_sources(client: AsyncClient, db_session):
    u, token = await _user(db_session)
    h = {"Authorization": f"Bearer {token}"}

    # create notebook
    nb_id = (
        await client.post("/api/notebooks", headers=h, json={"title": "n"})
    ).json()["id"]

    # upload (multipart)
    files = {"file": ("hello.mp4", b"fake-video-bytes-for-test", "video/mp4")}
    r = await client.post(
        f"/api/notebooks/{nb_id}/sources/upload",
        headers=h,
        files=files,
    )
    assert r.status_code == 201, r.text
    v1 = r.json()
    assert v1["source_type"] == "upload"
    assert v1["status"] in ("pending", "probing", "ready")  # 异步探查中
    assert v1["mime"] == "video/mp4"
    assert v1["content_hash"] is not None

    # fetch_url
    r = await client.post(
        f"/api/notebooks/{nb_id}/sources/fetch",
        headers=h,
        json={"url": "https://example.com/some.mp4"},
    )
    assert r.status_code == 201
    v2 = r.json()
    assert v2["source_type"] == "url"
    assert v2["source_url"] == "https://example.com/some.mp4"
    assert v2["status"] == "pending"

    # 列表里应该有 2 条
    r = await client.get(f"/api/notebooks/{nb_id}", headers=h)
    assert r.status_code == 200
    detail = r.json()
    assert detail["source_count"] == 2
    assert len(detail["sources"]) == 2

    # get video
    r = await client.get(f"/api/sources/{v1['id']}", headers=h)
    assert r.status_code == 200
    assert r.json()["id"] == v1["id"]

    # play_url 返回 internal proxy url
    r = await client.get(f"/api/sources/{v1['id']}/play_url", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["url"].startswith("/api/storage/")
    assert "token=" in body["url"]


async def test_play_url_404_when_no_storage_key(client: AsyncClient, db_session):
    u, token = await _user(db_session)
    h = {"Authorization": f"Bearer {token}"}
    nb_id = (await client.post("/api/notebooks", headers=h, json={"title": "n"})).json()["id"]
    r = await client.post(
        f"/api/notebooks/{nb_id}/sources/fetch",
        headers=h,
        json={"url": "https://example.com/x.mp4"},
    )
    vid = r.json()["id"]
    r = await client.get(f"/api/sources/{vid}/play_url", headers=h)
    assert r.status_code == 404


async def test_upload_rejects_empty_file(client: AsyncClient, db_session):
    u, token = await _user(db_session)
    h = {"Authorization": f"Bearer {token}"}
    nb_id = (await client.post("/api/notebooks", headers=h, json={"title": "n"})).json()["id"]
    files = {"file": ("empty.mp4", b"", "video/mp4")}
    r = await client.post(
        f"/api/notebooks/{nb_id}/sources/upload",
        headers=h,
        files=files,
    )
    assert r.status_code == 400


async def test_delete_source_unlinks_from_notebook(client: AsyncClient, db_session):
    u, token = await _user(db_session)
    h = {"Authorization": f"Bearer {token}"}
    nb_id = (await client.post("/api/notebooks", headers=h, json={"title": "n"})).json()["id"]
    files = {"file": ("a.mp4", b"abc", "video/mp4")}
    vid = (
        await client.post(
            f"/api/notebooks/{nb_id}/sources/upload", headers=h, files=files
        )
    ).json()["id"]

    r = await client.delete(f"/api/sources/{vid}", headers=h)
    assert r.status_code == 204
    r = await client.get(f"/api/notebooks/{nb_id}", headers=h)
    assert r.json()["source_count"] == 0


# ── Storage proxy ──────────────────────────────────────


async def test_storage_proxy_requires_token(client: AsyncClient, db_session):
    r = await client.get("/api/storage/abcdef1234567890")
    assert r.status_code == 401


async def test_storage_proxy_rejects_bad_token(client: AsyncClient, db_session):
    r = await client.get(
        "/api/storage/abcdef1234567890", params={"token": "garbage"}
    )
    assert r.status_code == 401


async def test_storage_proxy_returns_data_with_valid_token(client: AsyncClient, db_session):
    # 直接用 LocalFsStorage put 一些数据
    from app.storage import get_storage, reset_storage_singleton

    reset_storage_singleton()
    storage = get_storage()
    key = storage.put(data=b"hello-storage", content_type="text/plain", suffix=".txt")

    from app.core.config import get_settings

    settings = get_settings()
    import base64
    import hashlib
    import hmac
    import time as _time

    payload = f"{key}|{int(_time.time()) + 60}".encode()
    sig = hmac.new(settings.master_secret.encode(), payload, hashlib.sha256).digest()
    token = (
        base64.urlsafe_b64encode(payload).decode()
        + "."
        + base64.urlsafe_b64encode(sig).decode()
    )

    r = await client.get(f"/api/storage/{key}", params={"token": token})
    assert r.status_code == 200
    assert r.content == b"hello-storage"
    # Starlette 自动加 charset 尾巴；只比较 mime
    assert r.headers["content-type"].startswith("text/plain")
    assert r.headers["accept-ranges"] == "bytes"

    partial = await client.get(
        f"/api/storage/{key}",
        params={"token": token},
        headers={"Range": "bytes=0-4"},
    )
    assert partial.status_code == 206
    assert partial.content == b"hello"
