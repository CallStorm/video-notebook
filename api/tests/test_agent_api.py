"""Agent Token 鉴权与门面冒烟。"""
from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.core.errors import BadRequestError
from app.core.security import create_access_token
from app.models.notebook import Notebook, Video
from app.models.studio import StudioArtifact, StudioCapability, StudioTask
from app.models.user import User
from app.services.agent_tokens import hash_token
from app.storage import get_storage

pytestmark = pytest.mark.asyncio

_MARKER = b"NOT-IN-JSON-VIDEO-BYTES"


async def _user(db_session, phone: str = "13800001732") -> tuple[User, str]:
    user = User(phone=phone, name="代理", role="user", status="active")
    user.set_password("userpw1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token, _ = create_access_token(user.id, role=user.role)
    return user, token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _mint(client: AsyncClient, login: str, **body) -> tuple[dict, str]:
    payload = {
        "name": "Workbuddy",
        "scopes": ["read", "write_notebook", "write_generate"],
        "expires_in_days": None,
    }
    payload.update(body)
    response = await client.post("/api/users/me/agent-tokens", headers=_auth(login), json=payload)
    assert response.status_code == 201, response.text
    data = response.json()
    return data, data["plaintext"]


async def test_token_plaintext_shown_once_and_stored_hashed(client: AsyncClient, db_session):
    _user_row, login = await _user(db_session)
    created, plaintext = await _mint(client, login)
    assert plaintext.startswith("vn_agent_")
    assert created["install_command"].endswith(plaintext)
    assert "mcp_url" in created and created["mcp_url"].endswith("/mcp")

    from app.models.agent_token import AgentToken

    row = await db_session.get(AgentToken, created["token"]["id"])
    assert row is not None
    assert row.token_hash == hash_token(plaintext)
    assert plaintext not in row.token_hash
    assert row.token_hint == plaintext[-4:]
    assert row.name == "Workbuddy"

    listed = await client.get("/api/users/me/agent-tokens", headers=_auth(login))
    assert listed.status_code == 200
    body = listed.json()
    assert plaintext not in listed.text
    assert body["items"][0]["status"] == "active"
    assert body["items"][0]["name"] == "Workbuddy"
    assert "token_hash" not in body["items"][0]


async def test_agent_token_rejected_on_login_api_and_jwt_rejected_on_facade(
    client: AsyncClient, db_session
):
    _user_row, login = await _user(db_session, phone="13800001733")
    _created, plaintext = await _mint(client, login)

    denied = await client.get("/api/notebooks", headers=_auth(plaintext))
    assert denied.status_code == 401
    assert "登录 JWT" in denied.json()["message"]

    denied_agent = await client.post(
        "/agent/v1/tools/list_notebooks",
        headers=_auth(login),
        json={},
    )
    assert denied_agent.status_code == 401
    assert "登录 JWT" in denied_agent.json()["message"]

    missing = await client.post("/agent/v1/tools/list_notebooks", json={})
    assert missing.status_code == 401


async def test_revoked_and_expired_tokens_rejected(client: AsyncClient, db_session):
    _user_row, login = await _user(db_session, phone="13800001734")
    created, plaintext = await _mint(client, login, expires_in_days=30)
    ok = await client.post(
        "/agent/v1/tools/list_notebooks", headers=_auth(plaintext), json={}
    )
    assert ok.status_code == 200

    revoked = await client.post(
        f"/api/users/me/agent-tokens/{created['token']['id']}/revoke",
        headers=_auth(login),
    )
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"
    again = await client.post(
        "/agent/v1/tools/list_notebooks", headers=_auth(plaintext), json={}
    )
    assert again.status_code == 401

    _created2, live = await _mint(client, login, name="短期")
    from app.models.agent_token import AgentToken

    row = await db_session.get(AgentToken, _created2["token"]["id"])
    assert row is not None
    row.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5)
    db_session.add(row)
    await db_session.commit()
    expired = await client.post("/agent/v1/tools/list_notebooks", headers=_auth(live), json={})
    assert expired.status_code == 401
    assert "过期" in expired.json()["message"]


async def test_scope_blocks_create_and_create_returns_notebook_fields(
    client: AsyncClient, db_session
):
    _user_row, login = await _user(db_session, phone="13800001735")
    _created, readonly = await _mint(client, login, scopes=["read"], name="只读")
    blocked = await client.post(
        "/agent/v1/tools/create_notebook",
        headers=_auth(readonly),
        json={"name": "不该创建"},
    )
    assert blocked.status_code == 403

    _full, agent = await _mint(client, login)
    created = await client.post(
        "/agent/v1/tools/create_notebook",
        headers=_auth(agent),
        json={"name": "读书笔记", "description": "关于字幕"},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["name"] == "读书笔记"
    assert body["description"] == "关于字幕"
    assert body["cover_url"] is None
    assert body["notebook_id"]
    assert body["cover_job_id"]

    listed = await client.post(
        "/agent/v1/tools/list_notebooks", headers=_auth(agent), json={"search": "读书"}
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["notebook_id"] == body["notebook_id"]


async def test_add_url_readiness_and_download_url(client: AsyncClient, db_session):
    user, login = await _user(db_session, phone="13800001736")
    _created, agent = await _mint(client, login)
    notebook = await client.post(
        "/agent/v1/tools/create_notebook",
        headers=_auth(agent),
        json={"name": "来源本"},
    )
    notebook_id = notebook.json()["notebook_id"]

    added = await client.post(
        "/agent/v1/tools/add_url",
        headers=_auth(agent),
        json={"notebook_id": notebook_id, "url": "https://example.com/watch?v=1"},
    )
    assert added.status_code == 200, added.text
    video = added.json()["video"]
    assert "storage_key" not in video
    assert video["status"] == "pending"
    video_id = video["video_id"]

    readiness = await client.post(
        "/agent/v1/tools/get_readiness",
        headers=_auth(agent),
        json={"notebook_id": notebook_id},
    )
    assert readiness.status_code == 200
    assert readiness.json()["ready_for_draft"] is False

    row = await db_session.get(Video, video_id)
    assert row is not None
    row.status = "ready"
    row.subtitle_status = "ready"
    key = get_storage().put(data=_MARKER, content_type="video/mp4", suffix=".mp4")
    row.storage_key = key
    row.mime = "video/mp4"
    db_session.add(row)
    await db_session.commit()

    ready = await client.post(
        "/agent/v1/tools/get_readiness",
        headers=_auth(agent),
        json={"notebook_id": notebook_id},
    )
    assert ready.json()["ready_for_draft"] is True

    downloaded = await client.post(
        "/agent/v1/tools/download_video",
        headers=_auth(agent),
        json={"video_id": video_id},
    )
    assert downloaded.status_code == 200, downloaded.text
    payload = downloaded.json()
    assert payload["download_url"].startswith("http://testserver/api/storage/")
    assert "token=" in payload["download_url"]
    assert payload["expires_at"]
    assert _MARKER.decode() not in downloaded.text
    assert user.id == row.owner_id


async def test_cover_and_draft_jobs(client: AsyncClient, db_session, monkeypatch):
    _user_row, login = await _user(db_session, phone="13800001737")
    _created, agent = await _mint(client, login)
    created = await client.post(
        "/agent/v1/tools/create_notebook",
        headers=_auth(agent),
        json={"name": "封面本", "description": "一句话"},
    )
    notebook_id = created.json()["notebook_id"]
    cover_job_id = created.json()["cover_job_id"]

    queued = await client.post(
        "/agent/v1/tools/get_job",
        headers=_auth(agent),
        json={"job_id": cover_job_id},
    )
    assert queued.json()["status"] == "queued"

    async def fake_cover(session, *, title, description=None):
        del session, description
        assert title == "封面本"
        return {
            "cover_url": "/api/storage/placeholder",
            "storage_key": "storage:" + ("ab" * 20) + ".png",
        }

    monkeypatch.setattr("app.services.cover_generate.generate_cover", fake_cover)
    from app.services.agent_jobs import run_agent_job

    await run_agent_job(cover_job_id)
    done = await client.post(
        "/agent/v1/tools/get_job",
        headers=_auth(agent),
        json={"job_id": cover_job_id},
    )
    assert done.json()["status"] == "succeeded", done.text
    assert "/api/storage/" in (done.json()["result"]["cover_url"] or "")
    detail = await client.post(
        "/agent/v1/tools/get_notebook",
        headers=_auth(agent),
        json={"notebook_id": notebook_id},
    )
    assert "/api/storage/" in (detail.json()["cover_url"] or "")

    async def boom(session, *, title, description=None):
        del session, title, description
        raise BadRequestError("未配置封面模型")

    monkeypatch.setattr("app.services.cover_generate.generate_cover", boom)
    failed = await client.post(
        "/agent/v1/tools/generate_cover",
        headers=_auth(agent),
        json={"notebook_id": notebook_id},
    )
    assert failed.status_code == 200
    await run_agent_job(failed.json()["job_id"])
    failed_job = await client.post(
        "/agent/v1/tools/get_job",
        headers=_auth(agent),
        json={"job_id": failed.json()["job_id"]},
    )
    assert failed_job.json()["status"] == "failed"
    assert "封面" in (failed_job.json()["error"] or "")

    # generate_draft 与网页相同：写 StudioTask(knowledge_draft)，产物列表可见
    from app.models.notebook import NotebookSource, Video
    from app.models.studio import StudioCapability, StudioTask

    video = Video(
        owner_id=_user_row.id,
        source_type="upload",
        status="ready",
        subtitle_status="ready",
        overview_status="pending",
        title="底稿来源",
    )
    db_session.add(video)
    await db_session.flush()
    db_session.add(NotebookSource(notebook_id=notebook_id, video_id=video.id, selected_for_chat=True))
    cap = StudioCapability(
        name="知识底稿",
        format_key="knowledge_draft",
        enabled=True,
        is_builtin=True,
        form_json=[{"type": "sources"}, {"type": "text", "key": "focus", "label": "聚焦", "required": False}],
    )
    db_session.add(cap)
    await db_session.commit()

    monkeypatch.setattr("app.services.studio_tasks.enqueue_studio_task", lambda task_id: None)
    drafted = await client.post(
        "/agent/v1/tools/generate_draft",
        headers=_auth(agent),
        json={"notebook_id": notebook_id},
    )
    assert drafted.status_code == 200, drafted.text
    body = drafted.json()
    assert body["status"] == "queued"
    assert body["format_key"] == "knowledge_draft"
    assert body["job_id"] == body["task_id"]
    task = await db_session.get(StudioTask, body["task_id"])
    assert task is not None and task.format_key == "knowledge_draft"

    listed = await client.post(
        "/agent/v1/tools/list_artifacts",
        headers=_auth(agent),
        json={"notebook_id": notebook_id},
    )
    assert listed.status_code == 200, listed.text
    draft_items = [x for x in listed.json()["items"] if x.get("format_key") == "knowledge_draft"]
    assert draft_items and draft_items[0]["status"] == "queued"
    assert draft_items[0]["task_id"] == body["task_id"]

    task.status = "succeeded"
    db_session.add(task)
    await db_session.commit()
    draft_job = await client.post(
        "/agent/v1/tools/get_job",
        headers=_auth(agent),
        json={"job_id": body["job_id"]},
    )
    assert draft_job.json()["status"] == "succeeded", draft_job.text
    assert draft_job.json()["kind"] == "generate_draft"
    assert draft_job.json()["format_key"] == "knowledge_draft"


async def test_artifact_returns_signed_url_not_bytes(client: AsyncClient, db_session):
    user, login = await _user(db_session, phone="13800001738")
    _created, agent = await _mint(client, login)
    notebook = Notebook(owner_id=user.id, title="产物本", is_pinned=False, share_all=False)
    db_session.add(notebook)
    await db_session.flush()
    cap = StudioCapability(
        name="幻灯片",
        format_key="slides",
        enabled=True,
        is_builtin=True,
        form_json=[],
    )
    db_session.add(cap)
    await db_session.flush()
    task = StudioTask(
        notebook_id=notebook.id,
        owner_id=user.id,
        capability_id=cap.id,
        agent_id=None,
        format_key="slides",
        title="deck",
        status="succeeded",
        params_json={},
    )
    db_session.add(task)
    await db_session.flush()
    key = get_storage().put(data=_MARKER, content_type="application/pdf", suffix=".pdf")
    binary = StudioArtifact(
        task_id=task.id,
        role="main",
        filename="deck.pdf",
        mime="application/pdf",
        storage_key=key,
        text_content="should-not-leak",
    )
    text = StudioArtifact(
        task_id=task.id,
        role="side",
        filename="notes.md",
        mime="text/markdown",
        text_content="# 提纲",
    )
    db_session.add_all([binary, text])
    await db_session.commit()
    await db_session.refresh(binary)

    listed = await client.post(
        "/agent/v1/tools/list_artifacts",
        headers=_auth(agent),
        json={"notebook_id": notebook.id},
    )
    assert listed.status_code == 200
    listed_body = listed.json()
    assert {item["artifact_id"] for item in listed_body["items"]} == {binary.id, text.id}
    assert listed_body["draft"]["available"] is False
    assert listed_body["draft"]["read_with"] == "get_draft"

    fetched = await client.post(
        "/agent/v1/tools/get_artifact",
        headers=_auth(agent),
        json={"artifact_id": binary.id},
    )
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["download_url"].startswith("http://testserver/api/storage/")
    assert fetched.json()["text"] is None
    assert "should-not-leak" not in fetched.text
    assert _MARKER.decode() not in fetched.text

    prose = await client.post(
        "/agent/v1/tools/get_artifact",
        headers=_auth(agent),
        json={"artifact_id": text.id},
    )
    assert prose.json()["text"] == "# 提纲"
    assert prose.json()["download_url"] is None


async def test_public_docs_and_mcp(client: AsyncClient, db_session):
    from app.agent.facade import TOOLS

    skill = await client.get("/agent/skill.md")
    assert skill.status_code == 200
    text = skill.text
    for tool in TOOLS:
        assert tool.name in text
    assert "create_notebook" in text and "get_readiness" in text and "generate_draft" in text
    assert not re.search(r"vn_agent_[A-Za-z0-9_-]{16,}", text)
    assert "不要把 Token 写进" in text

    llms = await client.get("/llms.txt")
    assert llms.status_code == 200
    assert "search" in llms.text and "download_video" in llms.text

    script = await client.get("/agent/install.sh")
    assert script.status_code == 200
    assert "--token" in script.text
    assert "http://testserver" in script.text
    assert "skill.md" in script.text
    assert not re.search(r"vn_agent_[A-Za-z0-9_-]{16,}", script.text)

    spec = await client.get("/agent/openapi.json")
    assert spec.status_code == 200
    assert "/agent/v1/tools/create_notebook" in spec.json()["paths"]

    init = await client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )
    assert init.status_code == 200
    assert init.json()["result"]["serverInfo"]["name"] == "video-notebook"

    no_auth = await client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    )
    assert no_auth.status_code == 401

    _user_row, login = await _user(db_session, phone="13800001739")
    _created, agent = await _mint(client, login, name="MCP")
    jwt_call = await client.post(
        "/mcp",
        headers=_auth(login),
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "list_notebooks", "arguments": {}},
        },
    )
    assert jwt_call.status_code == 401

    listed = await client.post(
        "/mcp",
        headers=_auth(agent),
        json={"jsonrpc": "2.0", "id": 4, "method": "tools/list", "params": {}},
    )
    names = {item["name"] for item in listed.json()["result"]["tools"]}
    assert names == {tool.name for tool in TOOLS}

    called = await client.post(
        "/mcp",
        headers=_auth(agent),
        json={
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "list_notebooks", "arguments": {}},
        },
    )
    assert called.status_code == 200
    content = called.json()["result"]["content"][0]["text"]
    assert '"total": 0' in content or '"total":0' in content
    assert called.json()["result"]["isError"] is False
