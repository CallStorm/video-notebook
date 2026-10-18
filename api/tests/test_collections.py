"""Collection CRUD API."""
from __future__ import annotations

import pytest_asyncio

from app.core.security import create_access_token
from app.models.user import User


@pytest_asyncio.fixture
async def owner(db_session) -> User:
    user = User(phone="13800000801", name="CollOwner", role="user", status="active")
    user.set_password("userpw1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def owner_headers(owner) -> dict[str, str]:
    token, _ = create_access_token(owner.id, role=owner.role)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def outsider_headers(db_session) -> dict[str, str]:
    user = User(phone="13800000802", name="CollOut", role="user", status="active")
    user.set_password("userpw1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token, _ = create_access_token(user.id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


async def test_create_list_patch_delete_collection(client, owner_headers):
    created = await client.post(
        "/api/collections",
        headers=owner_headers,
        json={"name": "  分类1  "},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "分类1"
    assert body["icon"] is None
    assert body["notebook_count"] == 0

    listed = await client.get("/api/collections", headers=owner_headers)
    assert listed.status_code == 200
    assert any(row["id"] == body["id"] for row in listed.json())

    patched = await client.patch(
        f"/api/collections/{body['id']}",
        headers=owner_headers,
        json={"name": "分类壹", "icon": "📁"},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "分类壹"
    assert patched.json()["icon"] == "📁"

    cleared = await client.patch(
        f"/api/collections/{body['id']}",
        headers=owner_headers,
        json={"icon": ""},
    )
    assert cleared.status_code == 200
    assert cleared.json()["icon"] is None

    blank = await client.post(
        "/api/collections",
        headers=owner_headers,
        json={"name": "   "},
    )
    assert blank.status_code == 400

    deleted = await client.delete(f"/api/collections/{body['id']}", headers=owner_headers)
    assert deleted.status_code == 204
    missing = await client.get(f"/api/collections/{body['id']}", headers=owner_headers)
    assert missing.status_code == 404


async def test_outsider_cannot_see_collection(client, owner_headers, outsider_headers):
    created = await client.post(
        "/api/collections",
        headers=owner_headers,
        json={"name": "私有"},
    )
    cid = created.json()["id"]
    assert (await client.get(f"/api/collections/{cid}", headers=outsider_headers)).status_code == 404
