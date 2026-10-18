"""Admin agent create / disable / delete API."""
from __future__ import annotations

import pytest_asyncio

from app.core.security import create_access_token
from app.models.studio import StudioCapability
from app.models.user import User


@pytest_asyncio.fixture
async def admin_headers(db_session) -> dict[str, str]:
    admin = User(phone="13800000901", name="Admin", role="admin", status="active")
    admin.set_password("adminpw1234")
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    token, _ = create_access_token(admin.id, role="admin")
    return {"Authorization": f"Bearer {token}"}


async def test_disable_agent_turns_off_capabilities(client, admin_headers, db_session):
    created = await client.post(
        "/api/admin/agents",
        headers=admin_headers,
        json={
            "name": "导图智能体",
            "skill_id": None,
            "system_prompt": "写出导图",
            "timeout_seconds": 600,
        },
    )
    assert created.status_code == 201
    agent_id = created.json()["id"]
    cap = StudioCapability(
        name="思维导图",
        icon="🧠",
        format_key="mind_map",
        agent_id=agent_id,
        enabled=True,
        is_builtin=True,
        form_json=[],
    )
    db_session.add(cap)
    await db_session.commit()
    disabled = await client.post(f"/api/admin/agents/{agent_id}/disable", headers=admin_headers)
    assert disabled.status_code == 200
    await db_session.refresh(cap)
    assert cap.enabled is False
    removed = await client.delete(f"/api/admin/agents/{agent_id}", headers=admin_headers)
    assert removed.status_code == 409


async def test_create_agent_rejects_short_timeout(client, admin_headers):
    created = await client.post(
        "/api/admin/agents",
        headers=admin_headers,
        json={
            "name": "导图智能体",
            "skill_id": None,
            "system_prompt": "写出导图",
            "timeout_seconds": 10,
        },
    )
    assert created.status_code == 400
