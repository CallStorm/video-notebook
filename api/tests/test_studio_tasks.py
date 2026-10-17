"""Create and list studio tasks for a notebook owner."""
from __future__ import annotations

import pytest_asyncio

from app.core.security import create_access_token
from app.models.notebook import Notebook, NotebookSource, Video
from app.models.studio import Agent, StudioCapability
from app.models.user import User

_FORM = [
    {"type": "language"},
    {"type": "sources"},
    {"type": "text", "key": "topic", "label": "主题", "required": True, "multiline": False},
]


def _payload(capability_id: int, video_id: int, **overrides) -> dict:
    body = {
        "capability_id": capability_id,
        "language": "中文",
        "video_ids": [video_id],
        "note_ids": [],
        "fields": {"topic": "灭佛"},
    }
    body.update(overrides)
    return body


@pytest_asyncio.fixture
async def owner(db_session) -> User:
    user = User(phone="13800000601", name="Owner", role="user", status="active")
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
    user = User(phone="13800000602", name="Outsider", role="user", status="active")
    user.set_password("userpw1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token, _ = create_access_token(user.id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def notebook_id(db_session, owner) -> int:
    notebook = Notebook(owner_id=owner.id, title="本", is_pinned=False, share_all=False)
    db_session.add(notebook)
    await db_session.commit()
    await db_session.refresh(notebook)
    return notebook.id


@pytest_asyncio.fixture
async def capability_id(db_session, owner) -> int:
    agent = Agent(
        name="导图智能体",
        model_name="claude-sonnet-4-6",
        system_prompt="写出导图",
        is_active=True,
        updated_by=owner.id,
    )
    db_session.add(agent)
    await db_session.flush()
    cap = StudioCapability(
        name="思维导图",
        icon="🧠",
        format_key="mind_map",
        agent_id=agent.id,
        enabled=True,
        is_builtin=True,
        form_json=_FORM,
    )
    db_session.add(cap)
    await db_session.commit()
    await db_session.refresh(cap)
    return cap.id


@pytest_asyncio.fixture
async def video_id(db_session, owner, notebook_id) -> int:
    video = Video(
        owner_id=owner.id,
        source_type="upload",
        status="ready",
        subtitle_status="pending",
        overview_status="pending",
        title="选中的片子",
    )
    db_session.add(video)
    await db_session.flush()
    db_session.add(
        NotebookSource(
            notebook_id=notebook_id,
            video_id=video.id,
            sort=0,
            selected_for_chat=True,
        )
    )
    await db_session.commit()
    await db_session.refresh(video)
    return video.id


async def test_create_task_snapshots_and_rejects_outsider(client, owner_headers, outsider_headers, notebook_id, capability_id, video_id, monkeypatch):
    queued: list[int] = []
    monkeypatch.setattr(
        "app.services.studio_tasks.enqueue_studio_task",
        lambda task_id: queued.append(task_id),
    )
    created = await client.post(
        f"/api/notebooks/{notebook_id}/studio/tasks",
        headers=owner_headers,
        json={
            "capability_id": capability_id,
            "language": "中文",
            "video_ids": [video_id],
            "note_ids": [],
            "fields": {"topic": "灭佛"},
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "queued"
    assert body["format_key"] == "mind_map"
    assert body["title"] == "思维导图"
    assert queued == [body["id"]]
    hidden = await client.post(
        f"/api/notebooks/{notebook_id}/studio/tasks",
        headers=outsider_headers,
        json={
            "capability_id": capability_id,
            "language": "中文",
            "video_ids": [video_id],
            "note_ids": [],
            "fields": {"topic": "灭佛"},
        },
    )
    assert hidden.status_code == 404


async def test_create_task_rejects_blank_required_text(
    client, owner_headers, notebook_id, capability_id, video_id, monkeypatch
):
    monkeypatch.setattr("app.services.studio_tasks.enqueue_studio_task", lambda task_id: None)
    response = await client.post(
        f"/api/notebooks/{notebook_id}/studio/tasks",
        headers=owner_headers,
        json=_payload(capability_id, video_id, fields={"topic": ""}),
    )
    assert response.status_code == 400


async def test_create_task_rejects_empty_sources(
    client, owner_headers, notebook_id, capability_id, video_id, monkeypatch
):
    monkeypatch.setattr("app.services.studio_tasks.enqueue_studio_task", lambda task_id: None)
    response = await client.post(
        f"/api/notebooks/{notebook_id}/studio/tasks",
        headers=owner_headers,
        json=_payload(capability_id, video_id, video_ids=[], note_ids=[]),
    )
    assert response.status_code == 400


async def test_create_task_rejects_unknown_language(
    client, owner_headers, notebook_id, capability_id, video_id, monkeypatch
):
    monkeypatch.setattr("app.services.studio_tasks.enqueue_studio_task", lambda task_id: None)
    response = await client.post(
        f"/api/notebooks/{notebook_id}/studio/tasks",
        headers=owner_headers,
        json=_payload(capability_id, video_id, language="fr"),
    )
    assert response.status_code == 400


async def test_create_task_rejects_disabled_capability(
    client, owner_headers, notebook_id, capability_id, video_id, db_session, monkeypatch
):
    monkeypatch.setattr("app.services.studio_tasks.enqueue_studio_task", lambda task_id: None)
    cap = await db_session.get(StudioCapability, capability_id)
    cap.enabled = False
    await db_session.commit()
    response = await client.post(
        f"/api/notebooks/{notebook_id}/studio/tasks",
        headers=owner_headers,
        json=_payload(capability_id, video_id),
    )
    assert response.status_code == 400


async def test_list_capabilities_omits_disabled(
    client, owner_headers, notebook_id, capability_id, db_session
):
    disabled = StudioCapability(
        name="未启用",
        icon="x",
        format_key="file",
        enabled=False,
        is_builtin=False,
        form_json=[],
    )
    db_session.add(disabled)
    await db_session.commit()
    await db_session.refresh(disabled)
    response = await client.get(
        f"/api/notebooks/{notebook_id}/studio/capabilities",
        headers=owner_headers,
    )
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert capability_id in ids
    assert disabled.id not in ids


async def test_enqueue_failure_marks_task_failed(
    client, owner_headers, notebook_id, capability_id, video_id, monkeypatch
):
    def boom(_task_id: int) -> None:
        raise RuntimeError("broker down")

    monkeypatch.setattr("app.services.studio_tasks.enqueue_studio_task", boom)
    created = await client.post(
        f"/api/notebooks/{notebook_id}/studio/tasks",
        headers=owner_headers,
        json=_payload(capability_id, video_id),
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "failed"
    assert body["error_code"] == "process_failed"
