"""Cancel studio tasks and sweep leftover running work."""
from __future__ import annotations

import os
import socket
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.dml import Update

from app.core.errors import NotFoundError
from app.core.security import create_access_token
from app.db import session as session_module
from app.models.notebook import Notebook
from app.models.studio import Agent, StudioArtifact, StudioCapability, StudioTask
from app.models.user import User
from app.services.studio_tasks import delete_task
from app.storage import get_storage
from app.studio.runner import execute_studio_task
from app.studio.worker import studio_run, sweep_studio_tasks

_NOW = datetime(2026, 10, 18, 12, 0, 0)


async def _user(db_session, *, phone: str, name: str) -> User:
    user = User(phone=phone, name=name, role="user", status="active")
    user.set_password("userpw1234")
    db_session.add(user)
    await db_session.flush()
    return user


async def _seed_task(
    db_session,
    *,
    owner: User | None = None,
    status: str = "queued",
    timeout_seconds: int = 30,
    started_at: datetime | None = None,
    result_json: dict | None = None,
) -> tuple[User, StudioTask]:
    owner = owner or await _user(db_session, phone="13800000801", name="Owner")
    notebook = Notebook(owner_id=owner.id, title="本", is_pinned=False, share_all=False)
    db_session.add(notebook)
    await db_session.flush()
    agent = Agent(
        name="导图智能体",
        system_prompt="写出导图",
        timeout_seconds=timeout_seconds,
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
        form_json=[],
    )
    db_session.add(cap)
    await db_session.flush()
    task = StudioTask(
        notebook_id=notebook.id,
        owner_id=owner.id,
        capability_id=cap.id,
        agent_id=agent.id,
        format_key="mind_map",
        title=cap.name,
        status=status,
        params_json={"language": "中文", "video_ids": [], "note_ids": [], "fields": []},
        started_at=started_at,
        result_json=result_json,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return owner, task


@pytest_asyncio.fixture
async def owner_headers(db_session) -> tuple[User, dict[str, str]]:
    owner = await _user(db_session, phone="13800000811", name="RouteOwner")
    await db_session.commit()
    token, _ = create_access_token(owner.id, role=owner.role)
    return owner, {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def outsider_headers(db_session) -> dict[str, str]:
    user = await _user(db_session, phone="13800000812", name="Outsider")
    await db_session.commit()
    token, _ = create_access_token(user.id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


async def test_delete_queued_task_is_not_run(db_session):
    owner, task = await _seed_task(db_session)
    await delete_task(db_session, owner_id=owner.id, task_id=task.id)
    await execute_studio_task(task.id, claude_bin="/bin/false")
    await db_session.refresh(task)
    assert task.status == "canceled"
    assert task.deleted_at is not None


async def test_sweep_marks_stale_running_task_failed(db_session):
    owner, stale = await _seed_task(
        db_session,
        status="running",
        timeout_seconds=30,
        started_at=_NOW - timedelta(seconds=91),
    )
    _, fresh = await _seed_task(
        db_session,
        owner=owner,
        status="running",
        timeout_seconds=30,
        started_at=_NOW - timedelta(seconds=89),
    )
    await sweep_studio_tasks(_NOW)
    await db_session.refresh(stale)
    await db_session.refresh(fresh)
    assert stale.status == "failed"
    assert stale.error_code == "process_failed"
    assert fresh.status == "running"
    assert fresh.error_code is None


async def test_sweep_does_not_fail_task_that_became_succeeded(db_session, monkeypatch):
    _, task = await _seed_task(
        db_session,
        status="running",
        timeout_seconds=30,
        started_at=_NOW - timedelta(seconds=91),
    )
    original = AsyncSession.execute
    state = {"flipped": False}
    rowcounts: list[int] = []

    async def execute(self, statement, *args, **kwargs):
        if isinstance(statement, Update) and not state["flipped"]:
            state["flipped"] = True
            await original(
                self,
                update(StudioTask)
                .where(StudioTask.id == task.id)
                .values(status="succeeded", error_code=None),
            )
        result = await original(self, statement, *args, **kwargs)
        if isinstance(statement, Update):
            rowcounts.append(result.rowcount)
        return result

    monkeypatch.setattr(AsyncSession, "execute", execute)
    await sweep_studio_tasks(_NOW)
    await db_session.refresh(task)
    assert state["flipped"] is True
    assert rowcounts == [0]
    assert task.status == "succeeded"
    assert task.error_code is None


async def test_sweep_deletes_old_failure_work_dir(db_session, tmp_path):
    old_dir = tmp_path / "old_work"
    old_dir.mkdir()
    (old_dir / "stderr.log").write_text("boom", encoding="utf-8")
    old_mtime = datetime(2026, 10, 17, 11, 0, 0, tzinfo=UTC).timestamp()
    os.utime(old_dir, (old_mtime, old_mtime))
    new_dir = tmp_path / "new_work"
    new_dir.mkdir()
    (new_dir / "stderr.log").write_text("recent", encoding="utf-8")
    new_mtime = datetime(2026, 10, 18, 11, 0, 0, tzinfo=UTC).timestamp()
    os.utime(new_dir, (new_mtime, new_mtime))
    owner, old_task = await _seed_task(
        db_session,
        status="failed",
        result_json={"work_dir": str(old_dir)},
    )
    _, new_task = await _seed_task(
        db_session,
        owner=owner,
        status="failed",
        result_json={"work_dir": str(new_dir)},
    )
    await sweep_studio_tasks(_NOW)
    await db_session.refresh(old_task)
    await db_session.refresh(new_task)
    assert not old_dir.exists()
    assert new_dir.is_dir()
    assert old_task.status == "failed"
    assert new_task.status == "failed"


async def test_delete_finished_task_removes_storage_keys(db_session):
    owner, task = await _seed_task(db_session, status="succeeded")
    main_key = get_storage().put(data=b"# map\n", content_type="text/markdown", suffix=".md")
    side_key = get_storage().put(data=b"%PDF", content_type="application/pdf", suffix=".pdf")
    db_session.add(
        StudioArtifact(
            task_id=task.id,
            role="main",
            filename="mindmap.md",
            mime="text/markdown",
            storage_key=main_key,
            text_content="# map\n",
        )
    )
    db_session.add(
        StudioArtifact(
            task_id=task.id,
            role="side",
            filename="deck.pdf",
            mime="application/pdf",
            storage_key=side_key,
        )
    )
    await db_session.commit()
    await delete_task(db_session, owner_id=owner.id, task_id=task.id)
    await db_session.refresh(task)
    assert task.status == "succeeded"
    assert task.deleted_at is not None
    assert not get_storage().exists(main_key)
    assert not get_storage().exists(side_key)


async def test_delete_shared_storage_key_keeps_other_artifact(db_session):
    owner, first = await _seed_task(db_session, status="succeeded")
    _, second = await _seed_task(db_session, owner=owner, status="succeeded")
    key = get_storage().put(data=b"# shared\n", content_type="text/markdown", suffix=".md")
    db_session.add(
        StudioArtifact(
            task_id=first.id,
            role="main",
            filename="mindmap.md",
            mime="text/markdown",
            storage_key=key,
            text_content="# shared\n",
        )
    )
    db_session.add(
        StudioArtifact(
            task_id=second.id,
            role="main",
            filename="mindmap.md",
            mime="text/markdown",
            storage_key=key,
            text_content="# shared\n",
        )
    )
    await db_session.commit()
    await delete_task(db_session, owner_id=owner.id, task_id=first.id)
    await db_session.refresh(first)
    kept = (
        await db_session.execute(
            select(StudioArtifact).where(StudioArtifact.task_id == second.id)
        )
    ).scalar_one()
    assert first.deleted_at is not None
    assert get_storage().exists(key)
    assert kept.storage_key == key


async def test_delete_task_rejects_non_owner(db_session):
    owner, task = await _seed_task(db_session)
    outsider = await _user(db_session, phone="13800000802", name="Outsider")
    await db_session.commit()
    with pytest.raises(NotFoundError):
        await delete_task(db_session, owner_id=outsider.id, task_id=task.id)
    await db_session.refresh(task)
    assert task.status == "queued"
    assert task.deleted_at is None
    assert task.owner_id == owner.id


async def test_delete_running_task_is_canceled(db_session):
    owner, task = await _seed_task(
        db_session,
        status="running",
        started_at=_NOW,
    )
    await delete_task(db_session, owner_id=owner.id, task_id=task.id)
    await db_session.refresh(task)
    assert task.status == "canceled"
    assert task.deleted_at is not None


async def test_delete_route_owner_204_outsider_404(
    client, db_session, owner_headers, outsider_headers
):
    owner, headers = owner_headers
    _, task = await _seed_task(db_session, owner=owner)
    denied = await client.delete(f"/api/studio/tasks/{task.id}", headers=outsider_headers)
    assert denied.status_code == 404
    await db_session.refresh(task)
    assert task.deleted_at is None
    assert task.status == "queued"
    removed = await client.delete(f"/api/studio/tasks/{task.id}", headers=headers)
    assert removed.status_code == 204
    await db_session.refresh(task)
    assert task.status == "canceled"
    assert task.deleted_at is not None
    listed = await client.get(
        f"/api/notebooks/{task.notebook_id}/studio/tasks",
        headers=headers,
    )
    assert listed.status_code == 200
    assert listed.json() == []


def test_studio_run_disposes_engine(monkeypatch):
    saved_engine = session_module._engine
    saved_maker = session_module._sessionmaker

    class _DummyEngine:
        async def dispose(self) -> None:
            return None

    session_module._engine = _DummyEngine()
    session_module._sessionmaker = object()

    async def fake(_task_id: int) -> None:
        return None

    monkeypatch.setattr("app.studio.worker.execute_studio_task", fake)
    try:
        studio_run(1)
        assert session_module._engine is None
    finally:
        session_module._engine = saved_engine
        session_module._sessionmaker = saved_maker


def test_importing_worker_does_not_open_redis(monkeypatch):
    def blocked(*_args, **_kwargs):
        raise AssertionError("importing worker must not open a network connection")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    import importlib

    import app.studio.worker as worker_mod

    before = {thread.name for thread in threading.enumerate()}
    importlib.reload(worker_mod)
    after = {thread.name for thread in threading.enumerate()}
    assert worker_mod.celery_app.conf.broker_url
    assert Path(worker_mod.__file__).name == "worker.py"
    assert "studio-sweep" not in (after - before)
