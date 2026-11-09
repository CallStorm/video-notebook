"""首页列表带回字幕、概览计数，以及主人可见的失败原因和过期原因。"""
from __future__ import annotations

from datetime import datetime

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.knowledge_draft import NotebookKnowledgeDraft
from app.models.notebook import Note, Notebook, NotebookSource, Video
from app.models.notebook_index import NotebookIndexState
from app.models.user import User


async def _user(db_session, phone: str) -> tuple[User, str]:
    user = User(phone=phone, name=phone, role="user", status="active")
    user.set_password("userpw1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token, _ = create_access_token(user.id, role="user")
    return user, token


@pytest.mark.asyncio
async def test_notebook_list_reports_readiness_and_stale_reason(
    client: AsyncClient, db_session
):
    owner, token = await _user(db_session, "13800000941")
    indexed_at = datetime(2026, 1, 1, 8, 0, 0)
    notebook = Notebook(owner_id=owner.id, title="宏观课", is_pinned=False, share_all=False)
    ready = Video(
        owner_id=owner.id,
        source_type="upload",
        status="ready",
        storage_key="a.mp4",
        subtitle_status="ready",
        overview_status="ready",
        title="上",
    )
    failed = Video(
        owner_id=owner.id,
        source_type="upload",
        status="ready",
        storage_key="b.mp4",
        subtitle_status="ready",
        overview_status="failed",
        overview_error="模型超时",
        title="下",
    )
    db_session.add_all([notebook, ready, failed])
    await db_session.commit()
    await db_session.refresh(notebook)
    await db_session.refresh(ready)
    await db_session.refresh(failed)
    db_session.add_all(
        [
            NotebookSource(
                notebook_id=notebook.id, video_id=ready.id, sort=0, selected_for_chat=True
            ),
            NotebookSource(
                notebook_id=notebook.id, video_id=failed.id, sort=1, selected_for_chat=True
            ),
            NotebookIndexState(
                notebook_id=notebook.id, status="ready", indexed_at=indexed_at
            ),
            Note(
                notebook_id=notebook.id,
                author_id=owner.id,
                title="课后",
                content_text="新笔记",
                updated_at=datetime(2026, 2, 1, 8, 0, 0),
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(
        "/api/notebooks", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200, response.text
    item = next(row for row in response.json()["items"] if row["id"] == notebook.id)
    assert item["subtitle_ready"] == 2
    assert item["subtitle_failed"] == 0
    assert item["subtitle_total"] == 2
    assert item["overview_ready"] == 1
    assert item["overview_failed"] == 1
    assert item["overview_total"] == 2
    assert item["overview_error"] == "模型超时"
    assert item["index_status"] == "ready"
    assert item["index_stale_reason"] == "笔记有更新，尚未写入"


@pytest.mark.asyncio
async def test_conclusion_update_marks_index_stale(client: AsyncClient, db_session):
    owner, token = await _user(db_session, "13800000942")
    notebook = Notebook(owner_id=owner.id, title="读书笔记", is_pinned=False, share_all=False)
    db_session.add(notebook)
    await db_session.commit()
    await db_session.refresh(notebook)
    db_session.add_all(
        [
            NotebookIndexState(
                notebook_id=notebook.id,
                status="ready",
                indexed_at=datetime(2026, 1, 1, 8, 0, 0),
            ),
            NotebookKnowledgeDraft(
                notebook_id=notebook.id,
                owner_id=owner.id,
                conclusion="先看结构",
                content_json={"conclusions": ["先看结构"]},
                source_video_ids=[],
                source_note_ids=[],
                updated_at=datetime(2026, 3, 1, 8, 0, 0),
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(
        "/api/notebooks", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200, response.text
    item = next(row for row in response.json()["items"] if row["id"] == notebook.id)
    assert item["subtitle_total"] == 0
    assert item["index_stale_reason"] == "结论有更新，尚未写入"


@pytest.mark.asyncio
async def test_shared_notebook_hides_errors(client: AsyncClient, db_session):
    owner, _owner_token = await _user(db_session, "13800000943")
    viewer, viewer_token = await _user(db_session, "13800000944")
    notebook = Notebook(owner_id=owner.id, title="公开课", is_pinned=False, share_all=True)
    video = Video(
        owner_id=owner.id,
        source_type="upload",
        status="ready",
        storage_key="c.mp4",
        subtitle_status="failed",
        subtitle_error="识别失败",
        overview_status="pending",
        title="片",
    )
    db_session.add_all([notebook, video])
    await db_session.commit()
    await db_session.refresh(notebook)
    await db_session.refresh(video)
    db_session.add(
        NotebookSource(
            notebook_id=notebook.id, video_id=video.id, sort=0, selected_for_chat=True
        )
    )
    await db_session.commit()

    response = await client.get(
        "/api/notebooks/shared", headers={"Authorization": f"Bearer {viewer_token}"}
    )
    assert response.status_code == 200, response.text
    item = next(row for row in response.json()["items"] if row["id"] == notebook.id)
    assert item["subtitle_failed"] == 1
    assert item["subtitle_total"] == 1
    assert item["subtitle_error"] is None
    assert item["index_status"] is None
    assert item["index_stale_reason"] is None
    assert viewer.id != owner.id
