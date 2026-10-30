"""Admin studio: plugin seed; mind_map/slides always on (no admin toggles)."""
from __future__ import annotations

import pytest_asyncio
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.studio import StudioCapability
from app.models.user import User
from app.services.capabilities import ALWAYS_OFF_FORMATS, ALWAYS_ON_FORMATS


@pytest_asyncio.fixture
async def admin_headers(db_session) -> dict[str, str]:
    admin = User(phone="13800000902", name="Admin", role="admin", status="active")
    admin.set_password("adminpw1234")
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    token, _ = create_access_token(admin.id, role="admin")
    return {"Authorization": f"Bearer {token}"}


async def test_seed_forces_always_on_and_off(client, admin_headers, db_session):
    from app.services.capabilities import seed_builtin_capabilities

    await seed_builtin_capabilities(db_session)
    await seed_builtin_capabilities(db_session)
    rows = (
        await db_session.execute(
            select(StudioCapability).where(StudioCapability.is_builtin.is_(True))
        )
    ).scalars().all()
    keys = {row.format_key for row in rows}
    assert ALWAYS_ON_FORMATS <= keys
    for row in rows:
        if row.format_key in ALWAYS_ON_FORMATS:
            assert row.enabled is True
            assert row.agent_id is None
        if row.format_key in ALWAYS_OFF_FORMATS:
            assert row.enabled is False

    mind = next(row for row in rows if row.format_key == "mind_map")
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
    plugin_ids = {p["id"] for p in plugins.json()}
    assert ALWAYS_ON_FORMATS <= plugin_ids

    caps = await client.get("/api/admin/studio/capabilities", headers=admin_headers)
    assert caps.status_code == 200
    by_key = {c["format_key"]: c for c in caps.json()}
    assert by_key["mind_map"]["enabled"] is True
    assert by_key["slides"]["enabled"] is True


async def test_enable_disable_routes_removed(client, admin_headers, db_session):
    from app.services.capabilities import seed_builtin_capabilities

    await seed_builtin_capabilities(db_session)
    mind = (
        await db_session.execute(
            select(StudioCapability).where(StudioCapability.format_key == "mind_map")
        )
    ).scalar_one()

    enabled = await client.post(
        f"/api/admin/studio/capabilities/{mind.id}/enable",
        headers=admin_headers,
    )
    assert enabled.status_code in {404, 405}

    disabled = await client.post(
        f"/api/admin/studio/capabilities/{mind.id}/disable",
        headers=admin_headers,
    )
    assert disabled.status_code in {404, 405}


async def test_disable_always_on_refused_in_service(db_session):
    from app.core.errors import ConflictError
    from app.services.capabilities import disable_capability, seed_builtin_capabilities

    await seed_builtin_capabilities(db_session)
    mind = (
        await db_session.execute(
            select(StudioCapability).where(StudioCapability.format_key == "mind_map")
        )
    ).scalar_one()
    try:
        await disable_capability(db_session, mind.id)
        raise AssertionError("expected ConflictError")
    except ConflictError:
        pass


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
