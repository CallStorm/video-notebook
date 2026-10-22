"""发现页：他人 share_all 笔记本可见，且访客可读详情；私有本仍隔离。"""
from __future__ import annotations

from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.user import User


async def _user(db_session, phone="13800000881", name="分享者") -> tuple[User, str]:
    u = User(phone=phone, name=name, role="user", status="active")
    u.set_password("userpw1234")
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    token, _ = create_access_token(u.id, role="user")
    return u, token


async def test_shared_list_and_readable_detail(client: AsyncClient, db_session):
    owner, t1 = await _user(db_session, phone="13800000881", name="甲用户")
    viewer, t2 = await _user(db_session, phone="13800000882", name="乙用户")
    h1 = {"Authorization": f"Bearer {t1}"}
    h2 = {"Authorization": f"Bearer {t2}"}

    r = await client.post("/api/notebooks", headers=h1, json={"title": "公开减脂本", "description": "分享用"})
    assert r.status_code == 201, r.text
    nb_id = r.json()["id"]

    # 未公开：发现列表空，详情 404
    r = await client.get("/api/notebooks/shared", headers=h2)
    assert r.status_code == 200
    assert r.json()["total"] == 0
    r = await client.get(f"/api/notebooks/{nb_id}", headers=h2)
    assert r.status_code == 404

    # 公开
    r = await client.post(f"/api/notebooks/{nb_id}/share_all", headers=h1)
    assert r.status_code == 200
    assert r.json()["share_all"] is True

    # 发现列表出现（不含自己的）
    r = await client.get("/api/notebooks/shared", headers=h2)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["id"] == nb_id
    assert item["title"] == "公开减脂本"
    assert item["owner_name"] == "甲用户"
    assert item["is_owner"] is False
    assert item["share_all"] is True

    # 主人自己的发现列表不应出现自己的本
    r = await client.get("/api/notebooks/shared", headers=h1)
    assert r.status_code == 200
    assert r.json()["total"] == 0

    # 访客可读详情
    r = await client.get(f"/api/notebooks/{nb_id}", headers=h2)
    assert r.status_code == 200, r.text
    detail = r.json()
    assert detail["id"] == nb_id
    assert detail["is_owner"] is False
    assert detail["owner_name"] == "甲用户"
    assert detail["sources"] == []

    # 访客不能改 / 删
    r = await client.patch(f"/api/notebooks/{nb_id}", headers=h2, json={"title": "劫持"})
    assert r.status_code == 404
    r = await client.delete(f"/api/notebooks/{nb_id}", headers=h2)
    assert r.status_code == 404

    # 取消公开后再次隔离
    r = await client.delete(f"/api/notebooks/{nb_id}/share_all", headers=h1)
    assert r.status_code == 200
    assert r.json()["share_all"] is False
    r = await client.get("/api/notebooks/shared", headers=h2)
    assert r.json()["total"] == 0
    r = await client.get(f"/api/notebooks/{nb_id}", headers=h2)
    assert r.status_code == 404


async def test_private_still_isolated_from_shared_list(client: AsyncClient, db_session):
    _, t1 = await _user(db_session, phone="13800000891", name="私有主")
    _, t2 = await _user(db_session, phone="13800000892", name="路人")
    h1 = {"Authorization": f"Bearer {t1}"}
    h2 = {"Authorization": f"Bearer {t2}"}

    r = await client.post("/api/notebooks", headers=h1, json={"title": "私有本"})
    assert r.status_code == 201
    nb_id = r.json()["id"]

    r = await client.get("/api/notebooks/shared", headers=h2)
    assert r.json()["total"] == 0
    assert all(item["id"] != nb_id for item in r.json()["items"])
