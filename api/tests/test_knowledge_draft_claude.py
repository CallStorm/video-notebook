"""知识底稿走 Claude Code 任务：写回时保留结论，同时只允许一条在跑。"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.errors import BadRequestError
from app.core.security import create_access_token
from app.models.knowledge_draft import NotebookKnowledgeDraft
from app.models.notebook import Notebook, NotebookSource, Video
from app.models.studio import StudioCapability, StudioTask
from app.models.user import User
from app.services.knowledge_draft import merge_generated_draft


@pytest.mark.asyncio
async def test_merge_generated_draft_keeps_conclusions_and_comments(db_session):
    user = User(phone="13800000931", name="owner", role="user", status="active")
    user.set_password("userpw1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    notebook = Notebook(owner_id=user.id, title="交易", is_pinned=False, share_all=False)
    db_session.add(notebook)
    await db_session.commit()
    await db_session.refresh(notebook)
    db_session.add(
        NotebookKnowledgeDraft(
            notebook_id=notebook.id,
            owner_id=user.id,
            status="ready",
            conclusion="回撤到均线再观察",
            content_json={
                "theme": "旧主题",
                "concepts": [],
                "points": [
                    {
                        "id": "p1",
                        "text": "等待回撤",
                        "checked": True,
                        "comment": "这句我还想再看一遍",
                    }
                ],
                "takeaways": [],
                "open_questions": [],
                "conclusions": ["回撤到均线再观察"],
                "conclusion_checks": [
                    {
                        "text": "回撤到均线再观察",
                        "verdict": "partial",
                        "gap": "只说到附近",
                        "lines": [
                            {
                                "video_id": 1,
                                "line_no": 1,
                                "start_ms": 0,
                                "end_ms": 1000,
                                "text": "回撤到均线附近",
                            }
                        ],
                    }
                ],
            },
            source_video_ids=[1],
            source_note_ids=[],
        )
    )
    await db_session.commit()

    await merge_generated_draft(
        db_session,
        notebook_id=notebook.id,
        owner_id=user.id,
        raw_text=(
            '{"theme":"顺势","concepts":[],"points":['
            '{"text":"等待回撤","example":"像顺势游泳时利用浪谷调整"},'
            '{"text":"模型自己写的结论不该留下","example":"例"}],'
            '"conclusions":["模型结论"],"takeaways":["不要留下"]}'
        ),
        video_ids=[7],
        note_ids=[],
        focus="回撤",
    )
    await db_session.commit()
    row = (
        await db_session.execute(
            select(NotebookKnowledgeDraft).where(
                NotebookKnowledgeDraft.notebook_id == notebook.id
            )
        )
    ).scalar_one()
    assert row.model_ref == "claude_code"
    assert row.conclusion == "回撤到均线再观察"
    assert row.content_json["conclusions"] == ["回撤到均线再观察"]
    assert row.content_json["conclusion_checks"][0]["verdict"] == "partial"
    assert row.content_json["takeaways"] == []
    waiting = next(point for point in row.content_json["points"] if point["text"] == "等待回撤")
    assert waiting["comment"] == "这句我还想再看一遍"
    assert waiting["checked"] is False
    assert waiting["video_id"] == 7


@pytest.mark.asyncio
async def test_merge_rejects_a_draft_without_points(db_session):
    user = User(phone="13800000932", name="owner", role="user", status="active")
    user.set_password("userpw1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    notebook = Notebook(owner_id=user.id, title="空", is_pinned=False, share_all=False)
    db_session.add(notebook)
    await db_session.commit()
    await db_session.refresh(notebook)
    with pytest.raises(BadRequestError, match="底稿没有要点"):
        await merge_generated_draft(
            db_session,
            notebook_id=notebook.id,
            owner_id=user.id,
            raw_text='{"theme":"只有主题","points":[]}',
            video_ids=[],
            note_ids=[],
            focus=None,
        )


@pytest.mark.asyncio
async def test_only_one_knowledge_draft_task_runs(client: AsyncClient, db_session, monkeypatch):
    monkeypatch.setattr("app.services.studio_tasks.enqueue_studio_task", lambda _task_id: None)
    user = User(phone="13800000933", name="owner", role="user", status="active")
    user.set_password("userpw1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    notebook = Notebook(owner_id=user.id, title="本", is_pinned=False, share_all=False)
    video = Video(
        owner_id=user.id,
        source_type="upload",
        status="ready",
        subtitle_status="ready",
        overview_status="pending",
        title="片子",
    )
    db_session.add_all([notebook, video])
    await db_session.commit()
    await db_session.refresh(notebook)
    await db_session.refresh(video)
    db_session.add(
        NotebookSource(
            notebook_id=notebook.id,
            video_id=video.id,
            sort=0,
            selected_for_chat=True,
        )
    )
    cap = StudioCapability(
        name="知识底稿",
        icon="稿",
        format_key="knowledge_draft",
        agent_id=None,
        enabled=True,
        is_builtin=True,
        form_json=[
            {"type": "sources"},
            {"type": "text", "key": "focus", "label": "聚焦", "required": False},
        ],
    )
    db_session.add(cap)
    await db_session.commit()
    await db_session.refresh(cap)
    token, _ = create_access_token(user.id, role="user")
    headers = {"Authorization": f"Bearer {token}"}
    body = {
        "capability_id": cap.id,
        "video_ids": [video.id],
        "note_ids": [],
        "fields": {"focus": "回撤"},
    }
    first = await client.post(
        f"/api/notebooks/{notebook.id}/studio/tasks",
        headers=headers,
        json=body,
    )
    assert first.status_code == 201, first.text
    assert first.json()["status"] == "queued"
    second = await client.post(
        f"/api/notebooks/{notebook.id}/studio/tasks",
        headers=headers,
        json=body,
    )
    assert second.status_code == 400
    assert second.json()["message"] == "已有底稿正在生成"
    running = (
        await db_session.execute(
            select(StudioTask).where(StudioTask.notebook_id == notebook.id)
        )
    ).scalars().all()
    assert len(running) == 1
