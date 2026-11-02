"""Create and list studio tasks for a notebook owner."""
from __future__ import annotations

import pytest_asyncio

from app.core.security import create_access_token
from app.models.notebook import Note, Notebook, NotebookSource, Video
from app.models.studio import StudioArtifact, StudioCapability, StudioTask
from app.models.user import User
from app.storage import get_storage

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
    cap = StudioCapability(
        name="思维导图",
        icon="🧠",
        format_key="mind_map",
        agent_id=None,
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


@pytest_asyncio.fixture
async def note_id(db_session, owner, notebook_id) -> int:
    note = Note(
        notebook_id=notebook_id,
        author_id=owner.id,
        title="一条笔记",
        content_text="笔记全文",
        selected_for_chat=True,
    )
    db_session.add(note)
    await db_session.commit()
    await db_session.refresh(note)
    return note.id


async def test_patch_note_selection(client, owner_headers, notebook_id, note_id):
    response = await client.patch(
        f"/api/notebooks/{notebook_id}/notes/{note_id}",
        headers=owner_headers,
        json={"selected_for_chat": False},
    )
    assert response.status_code == 200
    assert response.json()["selected_for_chat"] is False


async def test_retry_failed_task_requeues(
    client, owner, owner_headers, outsider_headers, notebook_id, capability_id, db_session, monkeypatch
):
    queued: list[int] = []
    monkeypatch.setattr(
        "app.services.studio_tasks.enqueue_studio_task",
        lambda task_id: queued.append(task_id),
    )
    task = StudioTask(
        notebook_id=notebook_id,
        owner_id=owner.id,
        capability_id=capability_id,
        format_key="mind_map",
        title="失败的导图",
        status="failed",
        error_code="process_failed",
        error_message="claude exited 1",
        params_json={"language": "中文", "video_ids": [], "note_ids": [], "fields": []},
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    denied = await client.post(f"/api/studio/tasks/{task.id}/retry", headers=outsider_headers)
    assert denied.status_code == 404

    retried = await client.post(f"/api/studio/tasks/{task.id}/retry", headers=owner_headers)
    assert retried.status_code == 200, retried.text
    body = retried.json()
    assert body["status"] == "queued"
    assert body["error_code"] is None
    assert body["error_message"] is None
    assert queued == [task.id]

    again = await client.post(f"/api/studio/tasks/{task.id}/retry", headers=owner_headers)
    assert again.status_code == 400


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


async def test_get_task_returns_mind_map_text_for_owner_only(
    client, owner, owner_headers, outsider_headers, notebook_id, capability_id, db_session
):
    cap = await db_session.get(StudioCapability, capability_id)
    mind_map = StudioTask(
        notebook_id=notebook_id,
        owner_id=owner.id,
        capability_id=cap.id,
        agent_id=cap.agent_id,
        format_key="mind_map",
        title="灭佛",
        status="succeeded",
        params_json={"language": "中文", "video_ids": [1], "note_ids": [2], "fields": []},
    )
    queued = StudioTask(
        notebook_id=notebook_id,
        owner_id=owner.id,
        capability_id=cap.id,
        agent_id=cap.agent_id,
        format_key="mind_map",
        title="还在排队",
        status="queued",
        params_json={"language": "中文", "video_ids": [], "note_ids": [], "fields": []},
    )
    failed = StudioTask(
        notebook_id=notebook_id,
        owner_id=owner.id,
        capability_id=cap.id,
        agent_id=cap.agent_id,
        format_key="mind_map",
        title="失败的导图",
        status="failed",
        params_json={"language": "中文", "video_ids": [], "note_ids": [], "fields": []},
    )
    slides = StudioTask(
        notebook_id=notebook_id,
        owner_id=owner.id,
        capability_id=cap.id,
        agent_id=cap.agent_id,
        format_key="slides",
        title="一份幻灯片",
        status="succeeded",
        params_json={"language": "中文", "video_ids": [], "note_ids": [], "fields": []},
    )
    db_session.add_all([mind_map, queued, failed, slides])
    await db_session.flush()
    db_session.add(
        StudioArtifact(
            task_id=mind_map.id,
            role="main",
            filename="mindmap.md",
            mime="text/markdown",
            text_content="# 灭佛\n- 原因\n",
        )
    )
    db_session.add(
        StudioArtifact(
            task_id=failed.id,
            role="main",
            filename="mindmap.md",
            mime="text/markdown",
            text_content="# 不应返回\n",
        )
    )
    db_session.add(
        StudioArtifact(
            task_id=slides.id,
            role="main",
            filename="deck.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            text_content="should-not-leak",
        )
    )
    await db_session.commit()

    listed = await client.get(
        f"/api/notebooks/{notebook_id}/studio/tasks",
        headers=owner_headers,
    )
    assert listed.status_code == 200
    assert listed.json()
    assert all("text_content" not in item for item in listed.json())

    detail = await client.get(f"/api/studio/tasks/{mind_map.id}", headers=owner_headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == mind_map.id
    assert body["format_key"] == "mind_map"
    assert body["status"] == "succeeded"
    assert body["title"] == "灭佛"
    assert body["params_json"]["video_ids"] == [1]
    assert body["params_json"]["note_ids"] == [2]
    assert body["text_content"] == "# 灭佛\n- 原因\n"

    denied = await client.get(f"/api/studio/tasks/{mind_map.id}", headers=outsider_headers)
    assert denied.status_code == 404

    waiting = await client.get(f"/api/studio/tasks/{queued.id}", headers=owner_headers)
    assert waiting.status_code == 200
    assert waiting.json()["text_content"] is None

    broken = await client.get(f"/api/studio/tasks/{failed.id}", headers=owner_headers)
    assert broken.status_code == 200
    assert broken.json()["text_content"] is None

    deck = await client.get(f"/api/studio/tasks/{slides.id}", headers=owner_headers)
    assert deck.status_code == 200
    assert deck.json()["text_content"] is None
    assert "url" not in deck.json()


async def test_artifact_url_is_signed(
    client, owner, owner_headers, outsider_headers, notebook_id, capability_id, db_session
):
    cap = await db_session.get(StudioCapability, capability_id)
    slides = StudioTask(
        notebook_id=notebook_id,
        owner_id=owner.id,
        capability_id=cap.id,
        agent_id=cap.agent_id,
        format_key="slides",
        title="一份幻灯片",
        status="succeeded",
        params_json={"language": "中文", "video_ids": [], "note_ids": [], "fields": []},
        result_json={"pdf_error": "convert failed"},
    )
    mind_map = StudioTask(
        notebook_id=notebook_id,
        owner_id=owner.id,
        capability_id=cap.id,
        agent_id=cap.agent_id,
        format_key="mind_map",
        title="灭佛",
        status="succeeded",
        params_json={"language": "中文", "video_ids": [1], "note_ids": [], "fields": []},
    )
    db_session.add_all([slides, mind_map])
    await db_session.flush()
    pptx_bytes = b"PPTX-BYTES-not-in-json"
    pdf_bytes = b"PDF-BYTES-not-in-json"
    storage = get_storage()
    pptx_key = storage.put(
        data=pptx_bytes,
        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        suffix=".pptx",
    )
    pdf_key = storage.put(data=pdf_bytes, content_type="application/pdf", suffix=".pdf")
    main = StudioArtifact(
        task_id=slides.id,
        role="main",
        filename="deck.pptx",
        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        storage_key=pptx_key,
        text_content="should-not-leak",
    )
    side = StudioArtifact(
        task_id=slides.id,
        role="side",
        filename="deck.pdf",
        mime="application/pdf",
        storage_key=pdf_key,
    )
    db_session.add(
        StudioArtifact(
            task_id=mind_map.id,
            role="main",
            filename="mindmap.md",
            mime="text/markdown",
            text_content="# 灭佛\n- 原因\n",
        )
    )
    db_session.add_all([main, side])
    await db_session.commit()

    response = await client.get(
        f"/api/studio/tasks/{slides.id}/artifacts/{main.id}",
        headers=owner_headers,
    )
    assert response.status_code == 200
    assert response.json()["url"].startswith("/api/storage/")
    assert "token=" in response.json()["url"]
    assert response.json()["expires_in"] == 3600

    denied = await client.get(
        f"/api/studio/tasks/{slides.id}/artifacts/{main.id}",
        headers=outsider_headers,
    )
    assert denied.status_code == 404

    detail = await client.get(f"/api/studio/tasks/{slides.id}", headers=owner_headers)
    assert detail.status_code == 200
    deck = detail.json()
    assert deck["text_content"] is None
    assert "url" not in deck
    assert deck["pdf_error"] == "convert failed"
    assert {item["id"] for item in deck["artifacts"]} == {main.id, side.id}
    raw = detail.text
    assert pptx_bytes.decode() not in raw
    assert pdf_bytes.decode() not in raw
    assert "should-not-leak" not in raw
    assert pptx_key not in raw
    assert pdf_key not in raw

    mapped = await client.get(f"/api/studio/tasks/{mind_map.id}", headers=owner_headers)
    assert mapped.status_code == 200
    assert mapped.json()["text_content"] == "# 灭佛\n- 原因\n"


async def test_rename_task_updates_title_for_owner_only(
    client, owner_headers, outsider_headers, notebook_id, capability_id, video_id
):
    created = await client.post(
        f"/api/notebooks/{notebook_id}/studio/tasks",
        headers=owner_headers,
        json=_payload(capability_id, video_id),
    )
    assert created.status_code == 201
    task_id = created.json()["id"]

    renamed = await client.patch(
        f"/api/studio/tasks/{task_id}",
        headers=owner_headers,
        json={"title": "  灭佛 脑图  "},
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "灭佛 脑图"

    blank = await client.patch(
        f"/api/studio/tasks/{task_id}",
        headers=owner_headers,
        json={"title": "   "},
    )
    assert blank.status_code == 400

    denied = await client.patch(
        f"/api/studio/tasks/{task_id}",
        headers=outsider_headers,
        json={"title": "别人的名字"},
    )
    assert denied.status_code == 404
