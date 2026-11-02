"""发现检索文档包含笔记和我的结论。"""
from __future__ import annotations

import pytest

from app.models.knowledge_draft import NotebookKnowledgeDraft
from app.models.notebook import Note, Notebook
from app.models.user import User
from app.models.vector_settings import VectorSettingsConfig
from app.vector.document import build_notebook_document


@pytest.mark.asyncio
async def test_discover_document_includes_notes_and_conclusions(db_session):
    user = User(phone="13800000923", name="owner", role="user", status="active")
    user.set_password("userpw1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    notebook = Notebook(owner_id=user.id, title="交易", is_pinned=False, share_all=False)
    db_session.add(notebook)
    await db_session.commit()
    await db_session.refresh(notebook)
    db_session.add(
        Note(
            notebook_id=notebook.id,
            author_id=user.id,
            title="自己的笔记",
            content_text="回撤时先看均线方向",
            selected_for_chat=False,
        )
    )
    db_session.add(
        NotebookKnowledgeDraft(
            notebook_id=notebook.id,
            owner_id=user.id,
            status="ready",
            conclusion="我只做顺势回撤",
            content_json={
                "theme": "顺势",
                "concepts": [],
                "points": [],
                "takeaways": [],
                "open_questions": [],
                "conclusions": ["我只做顺势回撤"],
            },
            source_video_ids=[],
            source_note_ids=[],
        )
    )
    settings = VectorSettingsConfig(
        id=1,
        index_title=False,
        index_description=False,
        index_overview=False,
        index_subtitles=False,
        index_notes=False,
    )
    await db_session.commit()

    document = await build_notebook_document(db_session, notebook, settings)
    assert "回撤时先看均线方向" in document.text
    assert "我只做顺势回撤" in document.text
    assert "notes" in document.parts_used
    assert "conclusions" in document.parts_used
