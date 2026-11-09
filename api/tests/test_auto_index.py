"""笔记、底稿、笔记本和来源变化后自动排队索引。"""
from __future__ import annotations

import pytest

from app.models.knowledge_draft import NotebookKnowledgeDraft
from app.models.notebook import Notebook, NotebookSource, Video
from app.models.user import User
from app.schemas.knowledge_draft import KnowledgeDraftUpdateRequest
from app.services import knowledge_draft as draft_svc
from app.services import notebooks as notebooks_svc
from app.services import notes as notes_svc
from app.services import sources as sources_svc
from app.services import vector_settings as vector_svc
from app.schemas.vector_settings import VectorSettingsUpdate


def _capture(monkeypatch):
    calls: list[tuple[int, bool]] = []

    def fake(notebook_id: int, *, force: bool = False) -> None:
        calls.append((int(notebook_id), bool(force)))

    monkeypatch.setattr("app.vector.schedule.touch_notebook_index", fake)
    return calls


async def _owner(db_session) -> User:
    user = User(phone="13800000931", name="owner", role="user", status="active")
    user.set_password("userpw1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _notebook(db_session, user: User, *, title: str = "交易") -> Notebook:
    notebook = Notebook(owner_id=user.id, title=title, description="旧描述", share_all=False)
    db_session.add(notebook)
    await db_session.commit()
    await db_session.refresh(notebook)
    return notebook


@pytest.mark.asyncio
async def test_note_writes_schedule_index_selection_does_not(db_session, monkeypatch):
    calls = _capture(monkeypatch)
    user = await _owner(db_session)
    notebook = await _notebook(db_session, user)

    created = await notes_svc.create_blank_note(
        db_session, owner_id=user.id, notebook_id=notebook.id, title="一条笔记"
    )
    renamed = await notes_svc.rename_note(
        db_session,
        owner_id=user.id,
        note_id=created["id"],
        content_text="先看均线",
    )
    await notes_svc.set_note_selected(
        db_session,
        owner_id=user.id,
        notebook_id=notebook.id,
        note_id=renamed["id"],
        selected=False,
    )
    await notes_svc.delete_note(db_session, owner_id=user.id, note_id=renamed["id"])

    assert calls == [
        (notebook.id, False),
        (notebook.id, False),
        (notebook.id, False),
    ]


@pytest.mark.asyncio
async def test_draft_text_changes_schedule_index(db_session, monkeypatch):
    calls = _capture(monkeypatch)
    user = await _owner(db_session)
    notebook = await _notebook(db_session, user)
    db_session.add(
        NotebookKnowledgeDraft(
            notebook_id=notebook.id,
            owner_id=user.id,
            status="ready",
            conclusion="旧结论",
            content_json={
                "theme": "顺势",
                "concepts": [],
                "points": [{"id": "p1", "text": "旧要点", "checked": False}],
                "takeaways": [],
                "open_questions": [],
                "conclusions": ["旧结论"],
            },
            source_video_ids=[],
            source_note_ids=[],
        )
    )
    await db_session.commit()

    await draft_svc.update_draft(
        db_session,
        owner_id=user.id,
        notebook_id=notebook.id,
        body=KnowledgeDraftUpdateRequest(conclusions=["新结论"]),
    )
    await draft_svc.update_draft(
        db_session,
        owner_id=user.id,
        notebook_id=notebook.id,
        body=KnowledgeDraftUpdateRequest(point_text_updates={"p1": "新要点"}),
    )
    await draft_svc.delete_draft(
        db_session, owner_id=user.id, notebook_id=notebook.id
    )

    assert calls == [
        (notebook.id, False),
        (notebook.id, False),
        (notebook.id, False),
    ]


@pytest.mark.asyncio
async def test_notebook_text_share_and_delete_schedule_index(db_session, monkeypatch):
    calls = _capture(monkeypatch)
    user = await _owner(db_session)
    notebook = await _notebook(db_session, user)

    await notebooks_svc.update_notebook(
        db_session,
        owner_id=user.id,
        notebook_id=notebook.id,
        icon="📌",
    )
    await notebooks_svc.update_notebook(
        db_session,
        owner_id=user.id,
        notebook_id=notebook.id,
        title="新标题",
    )
    await notebooks_svc.set_share_all(
        db_session, owner_id=user.id, notebook_id=notebook.id, value=True
    )
    await notebooks_svc.delete_notebook(
        db_session, owner_id=user.id, notebook_id=notebook.id
    )

    assert calls == [
        (notebook.id, False),
        (notebook.id, False),
        (notebook.id, False),
    ]


@pytest.mark.asyncio
async def test_video_title_and_delete_schedule_linked_notebooks(db_session, monkeypatch):
    calls = _capture(monkeypatch)
    user = await _owner(db_session)
    first = await _notebook(db_session, user, title="甲")
    second = await _notebook(db_session, user, title="乙")
    video = Video(owner_id=user.id, source_type="upload", title="原标题", status="ready")
    db_session.add(video)
    await db_session.commit()
    await db_session.refresh(video)
    db_session.add(NotebookSource(notebook_id=first.id, video_id=video.id, sort=1))
    db_session.add(NotebookSource(notebook_id=second.id, video_id=video.id, sort=1))
    await db_session.commit()

    await sources_svc.rename_video(
        db_session, owner_id=user.id, video_id=video.id, title="新标题"
    )
    await sources_svc.delete_video(db_session, owner_id=user.id, video_id=video.id)

    assert calls == [
        (first.id, False),
        (second.id, False),
        (first.id, False),
        (second.id, False),
    ]


@pytest.mark.asyncio
async def test_index_flag_change_schedules_every_notebook(db_session, monkeypatch):
    calls = _capture(monkeypatch)
    user = await _owner(db_session)
    keep = await _notebook(db_session, user, title="留下")
    gone = await _notebook(db_session, user, title="删掉")
    await notebooks_svc.delete_notebook(
        db_session, owner_id=user.id, notebook_id=gone.id
    )
    calls.clear()

    await vector_svc.update_vector_settings(
        db_session,
        VectorSettingsUpdate(
            vector_backend="qdrant",
            qdrant_url="http://127.0.0.1:6333",
            qdrant_collection="notebooks",
            index_title=True,
            index_description=True,
            index_overview=True,
            index_subtitles=False,
            index_notes=True,
            index_conclusions=True,
            index_draft=True,
        ),
    )

    assert calls == [(keep.id, False)]


@pytest.mark.asyncio
async def test_chunk_limit_change_schedules_every_notebook(db_session, monkeypatch):
    calls = _capture(monkeypatch)
    user = await _owner(db_session)
    keep = await _notebook(db_session, user, title="分段")
    await vector_svc.update_vector_settings(
        db_session,
        VectorSettingsUpdate(
            vector_backend="qdrant",
            qdrant_url="http://127.0.0.1:6333",
            qdrant_collection="notebooks",
            chunk_subtitles_chars=4500,
        ),
    )
    calls.clear()
    await vector_svc.update_vector_settings(
        db_session,
        VectorSettingsUpdate(
            vector_backend="qdrant",
            qdrant_url="http://127.0.0.1:6333",
            qdrant_collection="notebooks",
            chunk_subtitles_chars=4500,
        ),
    )
    assert calls == []
    await vector_svc.update_vector_settings(
        db_session,
        VectorSettingsUpdate(
            vector_backend="qdrant",
            qdrant_url="http://127.0.0.1:6333",
            qdrant_collection="notebooks",
            chunk_subtitles_chars=3200,
        ),
    )
    assert calls == [(keep.id, False)]


@pytest.mark.asyncio
async def test_deleted_notebook_index_drops_vector(db_session, monkeypatch):
    from datetime import UTC, datetime

    from app.vector.indexer import index_notebook

    user = await _owner(db_session)
    notebook = await _notebook(db_session, user)
    notebook.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    await db_session.commit()
    deleted: list[int] = []

    class Store:
        async def delete(self, notebook_id: int) -> None:
            deleted.append(notebook_id)

    monkeypatch.setattr(
        "app.vector.indexer.make_vector_store", lambda **_kwargs: Store()
    )
    state = await index_notebook(db_session, notebook.id)
    assert state.status == "skipped"
    assert deleted == [notebook.id]


def test_debounced_index_keeps_only_latest_token(monkeypatch):
    store: dict[str, str] = {}

    class FakeRedis:
        def set(self, key, value, ex=None):
            store[key] = value

        def get(self, key):
            return store.get(key)

    monkeypatch.setattr("app.vector.enqueue._redis", lambda: FakeRedis())
    from app.vector.enqueue import arm_index_token, index_token_current

    first = arm_index_token(7)
    second = arm_index_token(7)
    assert first != second
    assert index_token_current(7, first) is False
    assert index_token_current(7, second) is True
    assert index_token_current(7, None) is True
