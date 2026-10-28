"""Admin studio: plugin seed + enable/disable (no page create/bind agent)."""
from __future__ import annotations

import pytest_asyncio
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.studio import StudioCapability
from app.models.user import User


@pytest_asyncio.fixture
async def admin_headers(db_session) -> dict[str, str]:
    admin = User(phone="13800000902", name="Admin", role="admin", status="active")
    admin.set_password("adminpw1234")
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    token, _ = create_access_token(admin.id, role="admin")
    return {"Authorization": f"Bearer {token}"}


async def test_seed_syncs_plugins_and_enable_without_agent(client, admin_headers, db_session):
    from app.services.capabilities import seed_builtin_capabilities

    await seed_builtin_capabilities(db_session)
    await seed_builtin_capabilities(db_session)
    rows = (
        await db_session.execute(
            select(StudioCapability).where(StudioCapability.is_builtin.is_(True))
        )
    ).scalars().all()
    assert {row.format_key for row in rows} == {"mind_map", "structured_notes", "slides"}
    mind = next(row for row in rows if row.format_key == "mind_map")
    assert mind.agent_id is None
    assert [field["type"] for field in mind.form_json] == [
        "language",
        "sources",
        "text",
        "select",
        "text",
    ]
    assert mind.form_json[2]["key"] == "topic"

    plugins = await client.get("/api/admin/studio/plugins", headers=admin_headers)
    assert plugins.status_code == 200
    assert {p["id"] for p in plugins.json()} == {"mind_map", "structured_notes", "slides"}

    enabled = await client.post(
        f"/api/admin/studio/capabilities/{mind.id}/enable",
        headers=admin_headers,
    )
    assert enabled.status_code == 200
    assert enabled.json()["enabled"] is True
    assert enabled.json()["agent_id"] is None

    disabled = await client.post(
        f"/api/admin/studio/capabilities/{mind.id}/disable",
        headers=admin_headers,
    )
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False


async def test_create_capability_rejected(client, admin_headers):
    created = await client.post(
        "/api/admin/studio/capabilities",
        headers=admin_headers,
        json={
            "name": "坏表单",
            "icon": "x",
            "format_key": "file",
            "agent_id": None,
            "form": [{"type": "sources"}],
        },
    )
    # Route removed → 405, or service raises 400 if somehow reached
    assert created.status_code in {400, 404, 405}


async def test_delete_route_removed(client, admin_headers, db_session):
    from app.services.capabilities import seed_builtin_capabilities

    await seed_builtin_capabilities(db_session)
    mind = (
        await db_session.execute(
            select(StudioCapability).where(StudioCapability.format_key == "mind_map")
        )
    ).scalar_one()
    deleted = await client.delete(
        f"/api/admin/studio/capabilities/{mind.id}",
        headers=admin_headers,
    )
    assert deleted.status_code in {404, 405}
