"""Admin Claude Code connection settings."""
from __future__ import annotations

from app.core.security import create_access_token
from app.models.studio import ClaudeCodeConfig
from app.models.user import User


async def _admin_headers(db_session) -> dict[str, str]:
    admin = User(phone="13800000911", name="Admin", role="admin", status="active")
    admin.set_password("adminpw1234")
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    token, _ = create_access_token(admin.id, role="admin")
    return {"Authorization": f"Bearer {token}"}


async def test_claude_config_hides_key_and_keeps_it_when_blank(client, db_session):
    headers = await _admin_headers(db_session)
    empty = await client.get("/api/admin/claude-code", headers=headers)
    assert empty.status_code == 200
    assert empty.json() == {"api_key_set": False, "base_url": None, "model_name": ""}

    missing_model = await client.put(
        "/api/admin/claude-code",
        headers=headers,
        json={"api_key": "sk-ant-test", "base_url": "", "model_name": "  "},
    )
    assert missing_model.status_code == 400

    saved = await client.put(
        "/api/admin/claude-code",
        headers=headers,
        json={
            "api_key": "sk-ant-test",
            "base_url": "https://example.test",
            "model_name": "claude-sonnet-4-6",
        },
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body == {
        "api_key_set": True,
        "base_url": "https://example.test",
        "model_name": "claude-sonnet-4-6",
    }
    assert "sk-ant-test" not in saved.text

    kept = await client.put(
        "/api/admin/claude-code",
        headers=headers,
        json={"api_key": "", "base_url": None, "model_name": "claude-opus-4-6"},
    )
    assert kept.status_code == 200
    assert kept.json()["api_key_set"] is True
    assert kept.json()["model_name"] == "claude-opus-4-6"
    assert kept.json()["base_url"] is None
    row = await db_session.get(ClaudeCodeConfig, 1)
    await db_session.refresh(row)
    assert row.get_api_key() == "sk-ant-test"


async def test_claude_config_rejects_non_admin(client, db_session):
    user = User(phone="13900000911", name="User", role="user", status="active")
    user.set_password("userpw1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token, _ = create_access_token(user.id, role="user")
    response = await client.get(
        "/api/admin/claude-code",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
