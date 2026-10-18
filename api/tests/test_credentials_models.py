"""Phase 3.5 重构后端到端：provider registry / credentials / models / default-models。"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.errors import BadRequestError
from app.core.security import create_access_token
from app.llm.provider_registry import (
    assert_provider_exists,
    provider_names,
)
from app.models.user import User

# pyproject sets `asyncio_mode = "auto"`：async 函数自动被识别为协程测试；
# sync 函数无 marker 也不会被误标。pytestmark.asyncio 反而会让 sync 测试报警告。


async def _admin(db_session) -> tuple[User, str]:
    admin = User(phone="13800000900", name="Admin", role="admin", status="active")
    admin.set_password("adminpw1234")
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    token, _ = create_access_token(admin.id, role="admin")
    return admin, token


async def _user_token(db_session) -> str:
    u = User(phone="13900000900", name="User", role="user", status="active")
    u.set_password("userpw1234")
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    token, _ = create_access_token(u.id, role="user")
    return token


# ─── provider registry ──────────────────────────────────────────────


def test_provider_registry_four_providers():
    assert provider_names() == ["minimax", "openai", "deepseek", "whisper"]


def test_assert_provider_exists_raises_on_unknown():
    with pytest.raises(BadRequestError):
        assert_provider_exists("no-such")
    spec = assert_provider_exists("minimax")
    assert spec.name == "minimax"


async def test_list_providers_endpoint(client: AsyncClient):
    """GET /api/providers 公开，不需 token。"""
    resp = await client.get("/api/providers")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "minimax" in names
    assert "whisper" in names
    for p in resp.json():
        assert "display_name" in p
        assert "modalities" in p
        assert isinstance(p["modalities"], list)


# ─── credentials ────────────────────────────────────────────────────


async def test_create_credential_minimax(client: AsyncClient, db_session):
    _, token = await _admin(db_session)
    resp = await client.post(
        "/api/admin/credentials",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "minimax-prod",
            "provider": "minimax",
            "api_key": "sk-minimax-test-1234567890",
            "base_url": "https://api.minimax.chat/v1",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["provider"] == "minimax"
    assert body["base_url"] == "https://api.minimax.chat/v1"
    assert body["has_api_key"] is True
    assert "sk-m" in body["api_key_masked"]
    assert "1234567890" not in body["api_key_masked"]  # 整段不外显


async def test_create_credential_unknown_provider_rejected(client: AsyncClient, db_session):
    _, token = await _admin(db_session)
    resp = await client.post(
        "/api/admin/credentials",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "x", "provider": "no-such-thing", "api_key": "sk-xxx"},
    )
    assert resp.status_code == 400


async def test_create_credential_modality_validation(client: AsyncClient, db_session):
    _, token = await _admin(db_session)
    resp = await client.post(
        "/api/admin/credentials",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "bad",
            "provider": "minimax",
            "api_key": "sk-x",
            "modalities": ["language", "embedding"],  # minimax 不支持 embedding
        },
    )
    assert resp.status_code == 400


async def test_credential_test_endpoint_uses_registry(client: AsyncClient, db_session, monkeypatch):
    _, token = await _admin(db_session)
    create = await client.post(
        "/api/admin/credentials",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "test-me", "provider": "minimax", "api_key": "sk-fake"},
    )
    assert create.status_code == 201
    cred_id = create.json()["id"]

    async def fake_test(provider, api_key, base_url=None):
        return {"ok": True, "latency_ms": 7, "provider": provider, "message": "fake-ok"}

    from app.routes import admin_credentials as r
    monkeypatch.setattr(r, "test_credential", fake_test)

    resp = await client.post(
        f"/api/admin/credentials/{cred_id}/test",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["message"] == "fake-ok"


async def test_credentials_require_admin_role(client: AsyncClient, db_session):
    user_token = await _user_token(db_session)
    resp = await client.get(
        "/api/admin/credentials",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 403


# ─── models + default_models ────────────────────────────────────────


async def test_create_model_requires_matching_credential(client: AsyncClient, db_session):
    _, token = await _admin(db_session)
    cred_resp = await client.post(
        "/api/admin/credentials",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "mm-1", "provider": "minimax", "api_key": "sk-x"},
    )
    assert cred_resp.status_code == 201
    cred_id = cred_resp.json()["id"]

    resp = await client.post(
        "/api/admin/models",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "minimax-text-01",
            "provider": "minimax",
            "type": "language",
            "credential_id": cred_id,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "minimax-text-01"
    assert body["provider"] == "minimax"
    assert body["type"] == "language"


async def test_create_model_credential_mismatch_rejected(client: AsyncClient, db_session):
    _, token = await _admin(db_session)
    mm_cred = await client.post(
        "/api/admin/credentials",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "mm-mm", "provider": "minimax", "api_key": "sk-x"},
    )
    resp = await client.post(
        "/api/admin/models",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "whisper-1",
            "provider": "whisper",
            "type": "speech_to_text",
            "credential_id": mm_cred.json()["id"],
        },
    )
    assert resp.status_code == 400


async def test_set_default_model_for_role(client: AsyncClient, db_session):
    _, token = await _admin(db_session)
    cred = await client.post(
        "/api/admin/credentials",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "mm-sd", "provider": "minimax", "api_key": "sk-x"},
    )
    assert cred.status_code == 201, cred.text
    cred_id = cred.json()["id"]
    model_resp = await client.post(
        "/api/admin/models",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "minimax-text-01-sd",
            "provider": "minimax",
            "type": "language",
            "credential_id": cred_id,
        },
    )
    assert model_resp.status_code == 201, model_resp.text
    model_id = model_resp.json()["id"]

    resp = await client.put(
        "/api/admin/default-models/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"model_id": model_id},
    )
    assert resp.status_code == 200
    assert resp.json() == {"role": "chat", "model_id": model_id}


async def test_set_default_unknown_role_rejected(client: AsyncClient, db_session):
    _, token = await _admin(db_session)
    resp = await client.put(
        "/api/admin/default-models/bogus",
        headers={"Authorization": f"Bearer {token}"},
        json={"model_id": 999},
    )
    assert resp.status_code == 400


async def test_list_default_models_returns_all_roles(client: AsyncClient, db_session):
    _, token = await _admin(db_session)
    resp = await client.get(
        "/api/admin/default-models",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    roles = [d["role"] for d in resp.json()]
    assert set(roles) == {"chat", "tts", "stt", "logo"}
