"""索引文档按后台开关拼接笔记、结论和底稿。"""
from __future__ import annotations

import pytest

from app.models.knowledge_draft import NotebookKnowledgeDraft
from app.models.notebook import Note, Notebook, NotebookSource, Subtitle, SubtitleLine, Video
from app.models.user import User
from app.models.vector_settings import VectorSettingsConfig
from app.vector.document import build_notebook_document, split_text


def _settings(**overrides: bool) -> VectorSettingsConfig:
    flags = {
        "index_title": False,
        "index_description": False,
        "index_overview": False,
        "index_subtitles": False,
        "index_notes": False,
        "index_conclusions": False,
        "index_draft": False,
    }
    flags.update(overrides)
    return VectorSettingsConfig(id=1, **flags)


async def _notebook(db_session) -> Notebook:
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
                "concepts": [{"term": "回撤", "definition": "上涨中的回调"}],
                "points": [
                    {
                        "id": "p1",
                        "text": "先看均线",
                        "evidence": "价格站上均线",
                        "example": "突破后等回踩",
                        "comment": "不追高",
                    }
                ],
                "takeaways": [{"id": "t1", "text": "等回撤再进场"}],
                "open_questions": ["多久算趋势结束"],
                "conclusions": ["我只做顺势回撤"],
            },
            source_video_ids=[],
            source_note_ids=[],
        )
    )
    await db_session.commit()
    return notebook


@pytest.mark.asyncio
async def test_index_flags_include_notes_conclusions_and_draft(db_session):
    notebook = await _notebook(db_session)
    document = await build_notebook_document(
        db_session,
        notebook,
        _settings(index_notes=True, index_conclusions=True, index_draft=True),
    )
    assert "回撤时先看均线方向" in document.text
    assert "我只做顺势回撤" in document.text
    assert "上涨中的回调" in document.text
    assert "价格站上均线" in document.text
    assert "突破后等回踩" in document.text
    assert "不追高" in document.text
    assert "等回撤再进场" in document.text
    assert "多久算趋势结束" in document.text
    assert "notes" in document.parts_used
    assert "conclusions" in document.parts_used
    assert "draft" in document.parts_used
    kinds = {chunk.part for chunk in document.chunks}
    assert kinds == {"notes", "conclusions", "draft"}
    note_chunks = [chunk for chunk in document.chunks if chunk.part == "notes"]
    assert len(note_chunks) == 1
    assert "回撤时先看均线方向" in note_chunks[0].text
    assert "我只做顺势回撤" not in note_chunks[0].text


@pytest.mark.asyncio
async def test_index_flags_can_leave_notes_conclusions_and_draft_out(db_session):
    notebook = await _notebook(db_session)
    document = await build_notebook_document(db_session, notebook, _settings())
    assert "回撤时先看均线方向" not in document.text
    assert "我只做顺势回撤" not in document.text
    assert "先看均线" not in document.text
    assert "notes" not in document.parts_used
    assert "conclusions" not in document.parts_used
    assert "draft" not in document.parts_used


@pytest.mark.asyncio
async def test_share_all_changes_index_hash(db_session):
    notebook = await _notebook(db_session)
    settings = _settings(index_notes=True)
    first = await build_notebook_document(db_session, notebook, settings)
    notebook.share_all = True
    second = await build_notebook_document(db_session, notebook, settings)
    assert first.content_hash != second.content_hash


@pytest.mark.asyncio
async def test_long_subtitles_keep_conclusions_inside_embedding_limit(db_session):
    user = User(phone="13800000924", name="owner", role="user", status="active")
    user.set_password("userpw1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    notebook = Notebook(owner_id=user.id, title="经济", description="宏观", share_all=False)
    db_session.add(notebook)
    await db_session.commit()
    await db_session.refresh(notebook)
    video = Video(
        owner_id=user.id,
        source_type="upload",
        title="讲座",
        status="ready",
        overview_text="概览很短",
        content_hash="a" * 40,
    )
    db_session.add(video)
    await db_session.commit()
    await db_session.refresh(video)
    db_session.add(NotebookSource(notebook_id=notebook.id, video_id=video.id, sort=1))
    subtitle = Subtitle(video_id=video.id, source="asr", language="zh", format="srt", line_count=1)
    db_session.add(subtitle)
    await db_session.commit()
    await db_session.refresh(subtitle)
    tail = "字幕末尾标记不应进入超长索引"
    db_session.add(
        SubtitleLine(
            subtitle_id=subtitle.id,
            line_no=1,
            start_ms=0,
            end_ms=1000,
            text=("口播" * 8000) + tail,
        )
    )
    db_session.add(
        NotebookKnowledgeDraft(
            notebook_id=notebook.id,
            owner_id=user.id,
            status="ready",
            conclusion="我的独特结论",
            content_json={
                "theme": "",
                "concepts": [],
                "points": [],
                "takeaways": [],
                "open_questions": [],
                "conclusions": ["我的独特结论"],
            },
            source_video_ids=[video.id],
            source_note_ids=[],
        )
    )
    await db_session.commit()

    document = await build_notebook_document(
        db_session,
        notebook,
        _settings(
            index_title=True,
            index_description=True,
            index_overview=True,
            index_subtitles=True,
            index_conclusions=True,
            chunk_subtitles_chars=6000,
            chunk_overlap_chars=200,
        ),
    )
    assert document.chunks
    assert all(len(chunk.text) <= 6000 + 20 for chunk in document.chunks)
    conclusion_chunks = [chunk for chunk in document.chunks if chunk.part == "conclusions"]
    subtitle_chunks = [chunk for chunk in document.chunks if chunk.part == "subtitles"]
    card_chunks = [chunk for chunk in document.chunks if chunk.part == "card"]
    assert len(conclusion_chunks) == 1
    assert "我的独特结论" in conclusion_chunks[0].text
    assert "口播" not in conclusion_chunks[0].text
    assert len(subtitle_chunks) >= 2
    assert any(tail in chunk.text for chunk in subtitle_chunks)
    assert all("我的独特结论" not in chunk.text for chunk in subtitle_chunks)
    assert len(card_chunks) == 1
    assert "概览很短" in card_chunks[0].text
    assert "口播" not in card_chunks[0].text
    assert "conclusions" in document.parts_used


def test_split_text_keeps_the_tail_and_overlaps():
    body = ("甲" * 2500) + "末尾"
    parts = split_text(body, limit=1000, overlap=100)
    assert len(parts) >= 3
    assert all(len(part) <= 1000 for part in parts)
    assert parts[-1].endswith("末尾")
    assert parts[0][-100:] == parts[1][:100]
