"""Admin studio capability CRUD, form validation, and builtin seed."""
from __future__ import annotations

import pytest_asyncio
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.notebook import Notebook
from app.models.studio import Agent, StudioCapability, StudioTask
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


async def test_seed_is_idempotent_and_enable_requires_agent(client, admin_headers, db_session):
    from app.services.capabilities import seed_builtin_capabilities

    await seed_builtin_capabilities(db_session)
    await seed_builtin_capabilities(db_session)
    rows = (
        await db_session.execute(
            select(StudioCapability).where(StudioCapability.is_builtin.is_(True))
        )
    ).scalars().all()
    assert {row.format_key for row in rows} == {"mind_map", "structured_notes", "slides"}
    assert all(row.enabled is False for row in rows)
    mind = next(row for row in rows if row.format_key == "mind_map")
    mind.name = "改过的名字"
    await db_session.commit()
    await seed_builtin_capabilities(db_session)
    await db_session.refresh(mind)
    assert mind.name == "改过的名字"
    assert [field["type"] for field in mind.form_json] == [
        "language",
        "sources",
        "text",
        "select",
        "text",
    ]
    assert mind.form_json[2]["key"] == "topic"
    assert mind.form_json[3]["key"] == "focus_mode"
    assert mind.form_json[3]["default"] == "action"
    assert mind.form_json[4]["key"] == "extra_constraints"
    denied = await client.post(
        f"/api/admin/studio/capabilities/{mind.id}/enable",
        headers=admin_headers,
    )
    assert denied.status_code == 409


async def test_create_rejects_duplicate_sources(client, admin_headers):
    created = await client.post(
        "/api/admin/studio/capabilities",
        headers=admin_headers,
        json={
            "name": "坏表单",
            "icon": "x",
            "format_key": "file",
            "agent_id": None,
            "form": [{"type": "sources"}, {"type": "sources"}],
        },
    )
    assert created.status_code == 400


async def test_patch_rejects_format_key(client, admin_headers, db_session):
    cap = StudioCapability(
        name="自建",
        icon="📝",
        format_key="file",
        enabled=False,
        is_builtin=False,
        form_json=[{"type": "sources"}],
    )
    db_session.add(cap)
    await db_session.commit()
    await db_session.refresh(cap)
    patched = await client.patch(
        f"/api/admin/studio/capabilities/{cap.id}",
        headers=admin_headers,
        json={"format_key": "slides"},
    )
    assert patched.status_code == 400


async def test_delete_builtin_and_capability_with_task(client, admin_headers, db_session):
    from app.services.capabilities import seed_builtin_capabilities

    await seed_builtin_capabilities(db_session)
    mind = (
        await db_session.execute(
            select(StudioCapability).where(StudioCapability.format_key == "mind_map")
        )
    ).scalar_one()
    builtin_denied = await client.delete(
        f"/api/admin/studio/capabilities/{mind.id}",
        headers=admin_headers,
    )
    assert builtin_denied.status_code == 409

    cap = StudioCapability(
        name="自建",
        icon="📝",
        format_key="file",
        enabled=False,
        is_builtin=False,
        form_json=[{"type": "sources"}],
    )
    db_session.add(cap)
    await db_session.flush()
    notebook = Notebook(owner_id=1, title="本")
    db_session.add(notebook)
    await db_session.flush()
    db_session.add(
        StudioTask(
            notebook_id=notebook.id,
            owner_id=1,
            capability_id=cap.id,
            agent_id=1,
            format_key="file",
            title="自建",
            status="queued",
            params_json={},
        )
    )
    await db_session.commit()
    await db_session.refresh(cap)
    in_use = await client.delete(
        f"/api/admin/studio/capabilities/{cap.id}",
        headers=admin_headers,
    )
    assert in_use.status_code == 409

    unused = StudioCapability(
        name="可删",
        icon="🗑",
        format_key="file",
        enabled=False,
        is_builtin=False,
        form_json=[],
    )
    db_session.add(unused)
    await db_session.commit()
    await db_session.refresh(unused)
    removed = await client.delete(
        f"/api/admin/studio/capabilities/{unused.id}",
        headers=admin_headers,
    )
    assert removed.status_code == 204


async def test_create_rejects_missing_agent(client, admin_headers):
    created = await client.post(
        "/api/admin/studio/capabilities",
        headers=admin_headers,
        json={
            "name": "无智能体",
            "icon": "x",
            "format_key": "file",
            "agent_id": 999999,
            "form": [],
        },
    )
    assert created.status_code == 400


async def test_patch_enabled_capability_rejects_null_agent(client, admin_headers, db_session):
    agent = Agent(
        name="可用",
        system_prompt="x",
        is_active=True,
        updated_by=1,
    )
    db_session.add(agent)
    await db_session.flush()
    cap = StudioCapability(
        name="已启用",
        icon="📝",
        format_key="file",
        agent_id=agent.id,
        enabled=True,
        is_builtin=False,
        form_json=[],
    )
    db_session.add(cap)
    await db_session.commit()
    await db_session.refresh(cap)
    patched = await client.patch(
        f"/api/admin/studio/capabilities/{cap.id}",
        headers=admin_headers,
        json={"agent_id": None},
    )
    assert patched.status_code == 409
    await db_session.refresh(cap)
    assert cap.enabled is True
    assert cap.agent_id == agent.id
