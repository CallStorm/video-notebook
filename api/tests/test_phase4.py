"""Phase 4：Notebook + Source 端到端。"""
from __future__ import annotations

from pathlib import Path

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


def _lexical_relative(start: Path, dest: Path) -> str:
    start_parts = start.parts
    dest_parts = dest.parts
    common = 0
    for left, right in zip(start_parts, dest_parts, strict=False):
        if left != right:
            break
        common += 1
    ups = len(start_parts) - common
    return "/".join([*[".."] * ups, *dest_parts[common:]])


async def test_signed_parent_key_rejected_and_valid_token_returns_bytes(
    client: AsyncClient,
):
    from urllib.parse import urlencode

    from app.core.errors import UnauthorizedError
    from app.main import create_app
    from app.routes.storage_proxy import stream_storage
    from app.storage import get_storage, reset_storage_singleton

    reset_storage_singleton()
    storage = get_storage()
    outside = storage.root.parent / f"{storage.root.name}-escape.bin"
    outside.write_bytes(b"TOP-SECRET-OUTSIDE-ROOT")
    try:
        digest = "ab" + "c" * 38
        leaf = storage.root / digest[:2] / f"{digest}.pdf"
        bad_key = f"{digest}.pdf/{_lexical_relative(leaf, outside)}"
        unsafe = (storage.root / digest[:2] / bad_key).resolve()
        assert ".." in bad_key
        assert unsafe == outside.resolve()
        assert not unsafe.is_relative_to(storage.root.resolve())

        bad_token = storage._make_token(bad_key, 60)  # noqa: SLF001
        assert storage.verify_signed_token(bad_key, bad_token, max_age_seconds=3600) is False
        with pytest.raises(ValueError):
            storage.local_path(bad_key)
        with pytest.raises(UnauthorizedError):
            await stream_storage(bad_key, token=bad_token)

        app = create_app()
        body = bytearray()
        status = {"code": 0}

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            elif message["type"] == "http.response.body":
                body.extend(message.get("body") or b"")

        path = f"/api/storage/{bad_key}"
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": urlencode({"token": bad_token}).encode(),
            "headers": [],
            "client": ("127.0.0.1", 123),
            "server": ("testserver", 80),
            "root_path": "",
        }
        await app(scope, receive, send)
        assert status["code"] == 401
        assert b"TOP-SECRET-OUTSIDE-ROOT" not in body

        payload = b"stored-bytes"
        key = storage.put(data=payload, content_type="text/plain", suffix=".txt")
        token = storage._make_token(key, 3600)  # noqa: SLF001
        ok = await client.get(f"/api/storage/{key}", params={"token": token})
        assert ok.status_code == 200
        assert ok.content == payload
        far = storage._make_token(key, 24 * 3600)  # noqa: SLF001
        rejected = await client.get(f"/api/storage/{key}", params={"token": far})
        assert rejected.status_code == 401
    finally:
        outside.unlink(missing_ok=True)
