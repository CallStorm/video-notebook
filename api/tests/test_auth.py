"""鉴权端点测试：用 sqlite 内存库跳过 mysql。"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.core.errors import UnauthorizedError
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.models.user import User

pytestmark = pytest.mark.asyncio


async def _make_user(*, phone="13800000000", password="password123", role="user") -> User:
    u = User(phone=phone, name="Test User", role=role, status="active")
    u.set_password(password)
    return u


async def test_login_success_and_returns_token_pair(client: AsyncClient, db_session):
    user = await _make_user()
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    resp = await client.post(
        "/api/auth/login",
        json={"phone": "13800000000", "password": "password123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == get_settings().jwt_access_ttl_seconds
    assert body["user"]["id"] == user.id
    assert body["user"]["role"] == "user"
    assert body["access"]
    assert body["refresh"]


async def test_login_wrong_password(client: AsyncClient, db_session):
    db_session.add(await _make_user())
    await db_session.commit()
    resp = await client.post(
        "/api/auth/login",
        json={"phone": "13800000000", "password": "WRONG-PW"},
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "unauthorized"


async def test_login_unknown_user(client: AsyncClient):
    resp = await client.post(
        "/api/auth/login",
        json={"phone": "19900000000", "password": "password123"},
    )
    assert resp.status_code == 401


async def test_login_validates_phone_format(client: AsyncClient):
    resp = await client.post(
        "/api/auth/login",
        json={"phone": "not-a-phone", "password": "password123"},
    )
    assert resp.status_code == 422


async def test_refresh_token_pair(client: AsyncClient, db_session):
    user = await _make_user()
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    refresh = create_refresh_token(user.id)
    resp = await client.post("/api/auth/refresh", json={"refresh": refresh})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access"] and body["refresh"]


async def test_refresh_rejects_access_token(client: AsyncClient, db_session):
    user = await _make_user()
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    access, _ = create_access_token(user.id, role=user.role)
    resp = await client.post("/api/auth/refresh", json={"refresh": access})
    assert resp.status_code == 401


async def test_get_me_requires_auth(client: AsyncClient):
    resp = await client.get("/api/users/me")
    assert resp.status_code == 401


async def test_get_me_returns_current_user(client: AsyncClient, db_session):
    user = await _make_user()
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    access, _ = create_access_token(user.id, role=user.role)
    resp = await client.get(
        "/api/users/me", headers={"Authorization": f"Bearer {access}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == user.id
    assert body["phone"] == "13800000000"


async def test_change_password(client: AsyncClient, db_session):
    user = await _make_user()
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    access, _ = create_access_token(user.id, role=user.role)
    resp = await client.post(
        "/api/users/me/change_password",
        headers={"Authorization": f"Bearer {access}"},
        json={"old_password": "password123", "new_password": "newpassword789"},
    )
    assert resp.status_code == 204
    # 旧密码应失败
    resp2 = await client.post(
        "/api/auth/login",
        json={"phone": "13800000000", "password": "password123"},
    )
    assert resp2.status_code == 401
    # 新密码应成功
    resp3 = await client.post(
        "/api/auth/login",
        json={"phone": "13800000000", "password": "newpassword789"},
    )
    assert resp3.status_code == 200


async def test_admin_endpoints_require_admin_role(client: AsyncClient, db_session):
    user = await _make_user(role="user")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    access, _ = create_access_token(user.id, role=user.role)

    resp = await client.get(
        "/api/admin/users", headers={"Authorization": f"Bearer {access}"}
    )
    assert resp.status_code == 403


async def test_admin_can_create_user_and_disable(client: AsyncClient, db_session):
    # 创建 admin
    admin = await _make_user(phone="13800000001", role="admin")
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    admin_token, _ = create_access_token(admin.id, role="admin")

    # 创建 user
    resp = await client.post(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"phone": "13800000002", "name": "Alice", "password": "password123"},
    )
    assert resp.status_code == 201
    new_id = resp.json()["id"]

    # 列表查询
    resp2 = await client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp2.status_code == 200
    assert any(u["id"] == new_id for u in resp2.json()["items"])

    # 禁用
    resp3 = await client.post(
        f"/api/admin/users/{new_id}/disable",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp3.status_code == 204


async def test_decode_token_unauthorized_message():
    """纯函数单元测试。"""
    with pytest.raises(UnauthorizedError):
        decode_token("garbage", expected_type="access")
