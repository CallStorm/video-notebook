"""对话：整段字幕进上下文，引用能对上字幕行。"""
from __future__ import annotations

import json

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.chat.context import CitedLine, parse_citations
from app.core.security import create_access_token
from app.llm.config_service import LlmResolved
from app.models.notebook import Note, Notebook, NotebookSource, Subtitle, SubtitleLine, Video
from app.models.user import User


def test_parse_citations_keeps_first_seen_order():
    lines = {
        1: CitedLine(1, 10, 3, "甲", "片"),
        2: CitedLine(2, 10, 8, "乙", "片"),
    }
    found = parse_citations("先看 [2]，再看 [1] 和 [2]，忽略 [9]", lines)
    assert [item["n"] for item in found] == [2, 1]
    assert found[0]["line_no"] == 8


_SUBTITLE_ONLY_SYSTEM = (
    "你是视频笔记助手。只能根据这次给出的字幕回答，不要编造字幕里没有的事实。"
    "依据某句字幕时，在句末用它前面的编号引用，例如 [1]。"
    "编号必须来自这次字幕，不要沿用历史回答里的编号，也不要自己发明。"
    "用中文回答。"
)
_NOTES_SYSTEM = (
    "你是视频笔记助手。可以根据这次给出的字幕和笔记回答，不要编造两者里都没有的事实。"
    "依据某句字幕时，在句末用它前面的编号引用，例如 [1]。"
    "编号必须来自这次字幕，不要沿用历史回答里的编号，也不要自己发明。"
    "笔记没有编号，不要给笔记编造 [n]。"
    "用中文回答。"
)


class _Provider:
    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.systems: list = []
        self.history: list | None = None

    async def stream_chat(self, prompt, *, system=None, history=None, **kwargs):
        self.prompts.append(prompt)
        self.systems.append(system)
        self.history = history
        yield "财政在收缩"
        yield "[1]"


async def _user(db_session, phone: str) -> tuple[User, str]:
    user = User(phone=phone, name=phone, role="user", status="active")
    user.set_password("userpw1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token, _ = create_access_token(user.id, role="user")
    return user, token


async def _notebook_with_lines(db_session, user: User) -> tuple[int, int, int]:
    notebook = Notebook(owner_id=user.id, title="笔记", is_pinned=False, share_all=False)
    selected = Video(
        owner_id=user.id,
        source_type="upload",
        status="ready",
        subtitle_status="ready",
        overview_status="pending",
        title="选中的片子",
    )
    ignored = Video(
        owner_id=user.id,
        source_type="upload",
        status="ready",
        subtitle_status="ready",
        overview_status="pending",
        title="没勾选",
    )
    db_session.add_all([notebook, selected, ignored])
    await db_session.commit()
    await db_session.refresh(notebook)
    await db_session.refresh(selected)
    await db_session.refresh(ignored)
    db_session.add_all(
        [
            NotebookSource(
                notebook_id=notebook.id,
                video_id=selected.id,
                sort=0,
                selected_for_chat=True,
            ),
            NotebookSource(
                notebook_id=notebook.id,
                video_id=ignored.id,
                sort=1,
                selected_for_chat=False,
            ),
        ]
    )
    subtitle = Subtitle(
        video_id=selected.id, source="asr", format="srt", line_count=1, version=1
    )
    other = Subtitle(
        video_id=ignored.id, source="asr", format="srt", line_count=1, version=1
    )
    db_session.add_all([subtitle, other])
    await db_session.commit()
    await db_session.refresh(subtitle)
    await db_session.refresh(other)
    db_session.add_all(
        [
            SubtitleLine(
                subtitle_id=subtitle.id,
                line_no=4,
                start_ms=0,
                end_ms=1000,
                text="财政在收缩",
            ),
            SubtitleLine(
                subtitle_id=other.id,
                line_no=1,
                start_ms=0,
                end_ms=1000,
                text="这段不该出现",
            ),
        ]
    )
    await db_session.commit()
    return notebook.id, selected.id, ignored.id


def _patch_llm(monkeypatch, provider: _Provider) -> None:
    async def fake_llm(_session):
        return LlmResolved(
            provider="minimax",
            base_url="https://api.minimaxi.com/v1",
            api_key="sk-test",
            model_name="MiniMax-M3",
            params_json=None,
        )

    monkeypatch.setattr("app.chat.service.get_active_llm", fake_llm)
    monkeypatch.setattr("app.chat.service.make_provider", lambda **kwargs: provider)


@pytest.mark.asyncio
async def test_chat_uses_selected_subtitles_and_saves_citation(
    client: AsyncClient, db_session, monkeypatch
):
    user, token = await _user(db_session, "13800000901")
    notebook_id, selected_id, _ignored = await _notebook_with_lines(db_session, user)
    provider = _Provider()
    _patch_llm(monkeypatch, provider)
    headers = {"Authorization": f"Bearer {token}"}

    async with client.stream(
        "POST",
        f"/api/notebooks/{notebook_id}/chat",
        headers=headers,
        json={"message": "在说什么？", "source_ids": [selected_id]},
    ) as response:
        assert response.status_code == 200, await response.aread()
        raw = (await response.aread()).decode()

    events = [
        json.loads(line.removeprefix("data: "))
        for line in raw.splitlines()
        if line.startswith("data: ")
    ]
    assert any(event["type"] == "token" for event in events)
    done = events[-1]
    assert done["type"] == "done"
    assert done["citations"] == [
        {
            "n": 1,
            "source_id": selected_id,
            "line_no": 4,
            "snippet": "财政在收缩",
            "title": "选中的片子",
        }
    ]
    assert "财政在收缩" in provider.prompts[0]
    assert "这段不该出现" not in provider.prompts[0]

    history = await client.get(f"/api/notebooks/{notebook_id}/chat", headers=headers)
    assert history.status_code == 200
    messages = history.json()["messages"]
    assert [item["role"] for item in messages] == ["user", "assistant"]
    assert messages[1]["citations"][0]["line_no"] == 4


@pytest.mark.asyncio
async def test_chat_rejects_when_nothing_selected(client: AsyncClient, db_session, monkeypatch):
    user, token = await _user(db_session, "13800000902")
    notebook_id, selected_id, _ignored = await _notebook_with_lines(db_session, user)
    _patch_llm(monkeypatch, _Provider())
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.patch(
        f"/api/notebooks/{notebook_id}/sources/{selected_id}",
        headers=headers,
        json={"selected_for_chat": False},
    )
    assert response.status_code == 200

    response = await client.post(
        f"/api/notebooks/{notebook_id}/chat",
        headers=headers,
        json={"message": "在说什么？"},
    )
    assert response.status_code == 400
    assert "勾选" in response.json()["message"]


@pytest.mark.asyncio
async def test_save_answer_as_note_once(client: AsyncClient, db_session, monkeypatch):
    user, token = await _user(db_session, "13800000904")
    notebook_id, selected_id, _ignored = await _notebook_with_lines(db_session, user)
    _patch_llm(monkeypatch, _Provider())
    headers = {"Authorization": f"Bearer {token}"}
    async with client.stream(
        "POST",
        f"/api/notebooks/{notebook_id}/chat",
        headers=headers,
        json={"message": "在说什么？", "source_ids": [selected_id]},
    ) as response:
        assert response.status_code == 200
        await response.aread()

    history = await client.get(f"/api/notebooks/{notebook_id}/chat", headers=headers)
    answer = next(item for item in history.json()["messages"] if item["role"] == "assistant")
    assert answer["note_id"] is None

    saved = await client.post(f"/api/messages/{answer['id']}/save_as_note", headers=headers)
    assert saved.status_code == 200, saved.text
    note = saved.json()
    assert note["message_id"] == answer["id"]
    assert "财政在收缩" in note["content_text"]
    again = await client.post(f"/api/messages/{answer['id']}/save_as_note", headers=headers)
    assert again.json()["id"] == note["id"]

    detail = await client.get(f"/api/notebooks/{notebook_id}", headers=headers)
    assert detail.json()["note_count"] == 1
    assert detail.json()["notes"][0]["id"] == note["id"]
    history = await client.get(f"/api/notebooks/{notebook_id}/chat", headers=headers)
    answer = next(item for item in history.json()["messages"] if item["role"] == "assistant")
    assert answer["note_id"] == note["id"]

    renamed = await client.patch(
        f"/api/notes/{note['id']}", headers=headers, json={"title": "灭佛之源"}
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "灭佛之源"

    removed = await client.delete(f"/api/notes/{note['id']}", headers=headers)
    assert removed.status_code == 204
    detail = await client.get(f"/api/notebooks/{notebook_id}", headers=headers)
    assert detail.json()["note_count"] == 0
    history = await client.get(f"/api/notebooks/{notebook_id}/chat", headers=headers)
    answer = next(item for item in history.json()["messages"] if item["role"] == "assistant")
    assert answer["note_id"] is None


@pytest.mark.asyncio
async def test_select_all_sources(client: AsyncClient, db_session):
    user, token = await _user(db_session, "13800000903")
    notebook_id, _selected, ignored_id = await _notebook_with_lines(db_session, user)
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.patch(
        f"/api/notebooks/{notebook_id}/sources/selection",
        headers=headers,
        json={"selected_for_chat": True},
    )
    assert response.status_code == 200
    detail = await client.get(f"/api/notebooks/{notebook_id}", headers=headers)
    flags = {item["video_id"]: item["selected_for_chat"] for item in detail.json()["sources"]}
    assert flags[ignored_id] is True


@pytest_asyncio.fixture
async def user(db_session) -> User:
    row, _token = await _user(db_session, "13800000910")
    return row


@pytest.mark.asyncio
async def test_chat_without_note_ids_stays_on_videos(client, db_session, user, monkeypatch):
    notebook_id, selected_id, _ignored = await _notebook_with_lines(db_session, user)
    note = Note(
        notebook_id=notebook_id,
        author_id=user.id,
        title="旁注",
        content_text="笔记里的句子",
        selected_for_chat=True,
    )
    db_session.add(note)
    await db_session.commit()
    captured: dict = {}

    async def fake_stream(prepared):
        captured["prompt"] = prepared.prompt
        yield {"type": "done", "message_id": None, "citations": []}

    monkeypatch.setattr("app.chat.service.stream_answer", fake_stream)
    _patch_llm(monkeypatch, _Provider())
    token, _ = create_access_token(user.id, role=user.role)
    await client.post(
        f"/api/notebooks/{notebook_id}/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "在说什么？", "source_ids": [selected_id]},
    )
    assert "笔记里的句子" not in captured["prompt"]


@pytest.mark.asyncio
async def test_chat_with_note_ids_appends_note_after_subtitles(
    client, db_session, user, monkeypatch
):
    notebook_id, selected_id, _ignored = await _notebook_with_lines(db_session, user)
    note = Note(
        notebook_id=notebook_id,
        author_id=user.id,
        title="旁注",
        content_text="笔记里的句子",
        selected_for_chat=True,
    )
    db_session.add(note)
    await db_session.commit()
    await db_session.refresh(note)
    captured: dict = {}

    async def fake_stream(prepared):
        captured["prompt"] = prepared.prompt
        captured["citations"] = prepared.context.lines
        yield {"type": "done", "message_id": None, "citations": []}

    monkeypatch.setattr("app.chat.service.stream_answer", fake_stream)
    _patch_llm(monkeypatch, _Provider())
    token, _ = create_access_token(user.id, role=user.role)
    response = await client.post(
        f"/api/notebooks/{notebook_id}/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "message": "在说什么？",
            "source_ids": [selected_id],
            "note_ids": [note.id],
        },
    )
    assert response.status_code == 200, response.text
    prompt = captured["prompt"]
    assert "财政在收缩" in prompt
    assert "笔记里的句子" in prompt
    assert "笔记：旁注\n笔记里的句子" in prompt
    subtitle_index = prompt.index("财政在收缩")
    note_index = prompt.index("笔记里的句子")
    assert subtitle_index < note_index
    assert prompt.index("问题：") > note_index
    assert list(captured["citations"]) == [1]


@pytest.mark.asyncio
async def test_chat_note_not_in_notebook_returns_404(client, db_session, user, monkeypatch):
    notebook_id, selected_id, _ignored = await _notebook_with_lines(db_session, user)
    other = Notebook(owner_id=user.id, title="另一本", is_pinned=False, share_all=False)
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)
    note = Note(
        notebook_id=other.id,
        author_id=user.id,
        title="旁注",
        content_text="笔记里的句子",
        selected_for_chat=True,
    )
    db_session.add(note)
    await db_session.commit()
    await db_session.refresh(note)

    async def fake_stream(prepared):
        yield {"type": "done", "message_id": None, "citations": []}

    monkeypatch.setattr("app.chat.service.stream_answer", fake_stream)
    _patch_llm(monkeypatch, _Provider())
    token, _ = create_access_token(user.id, role=user.role)
    response = await client.post(
        f"/api/notebooks/{notebook_id}/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "message": "在说什么？",
            "source_ids": [selected_id],
            "note_ids": [note.id],
        },
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_chat_notes_without_videos_skips_subtitle_requirement(
    client, db_session, user, monkeypatch
):
    notebook = Notebook(owner_id=user.id, title="只有笔记", is_pinned=False, share_all=False)
    db_session.add(notebook)
    await db_session.commit()
    await db_session.refresh(notebook)
    note = Note(
        notebook_id=notebook.id,
        author_id=user.id,
        title="旁注",
        content_text="笔记里的句子",
        selected_for_chat=True,
    )
    db_session.add(note)
    await db_session.commit()
    await db_session.refresh(note)
    captured: dict = {}

    async def fake_stream(prepared):
        captured["prompt"] = prepared.prompt
        yield {"type": "done", "message_id": None, "citations": []}

    monkeypatch.setattr("app.chat.service.stream_answer", fake_stream)
    _patch_llm(monkeypatch, _Provider())
    token, _ = create_access_token(user.id, role=user.role)
    response = await client.post(
        f"/api/notebooks/{notebook.id}/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "message": "在说什么？",
            "source_ids": [],
            "note_ids": [note.id],
        },
    )
    assert response.status_code == 200, response.text
    assert "笔记：旁注\n笔记里的句子" in captured["prompt"]


@pytest.mark.asyncio
async def test_chat_multiple_notes_separated_by_blank_line(
    client, db_session, user, monkeypatch
):
    notebook_id, selected_id, _ignored = await _notebook_with_lines(db_session, user)
    first = Note(
        notebook_id=notebook_id,
        author_id=user.id,
        title="旁注",
        content_text="笔记里的句子",
        selected_for_chat=True,
    )
    second = Note(
        notebook_id=notebook_id,
        author_id=user.id,
        title="另一篇",
        content_text="第二句",
        selected_for_chat=True,
    )
    db_session.add_all([first, second])
    await db_session.commit()
    await db_session.refresh(first)
    await db_session.refresh(second)
    captured: dict = {}

    async def fake_stream(prepared):
        captured["prompt"] = prepared.prompt
        yield {"type": "done", "message_id": None, "citations": []}

    monkeypatch.setattr("app.chat.service.stream_answer", fake_stream)
    _patch_llm(monkeypatch, _Provider())
    token, _ = create_access_token(user.id, role=user.role)
    response = await client.post(
        f"/api/notebooks/{notebook_id}/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "message": "在说什么？",
            "source_ids": [selected_id],
            "note_ids": [first.id, second.id],
        },
    )
    assert response.status_code == 200, response.text
    assert "笔记：旁注\n笔记里的句子\n\n笔记：另一篇\n第二句" in captured["prompt"]


@pytest.mark.asyncio
async def test_chat_system_prompt_allows_notes_only_when_note_ids_present(
    client, db_session, user, monkeypatch
):
    notebook_id, selected_id, _ignored = await _notebook_with_lines(db_session, user)
    note = Note(
        notebook_id=notebook_id,
        author_id=user.id,
        title="旁注",
        content_text="笔记里的句子",
        selected_for_chat=True,
    )
    db_session.add(note)
    await db_session.commit()
    await db_session.refresh(note)
    token, _ = create_access_token(user.id, role=user.role)
    headers = {"Authorization": f"Bearer {token}"}

    without_notes = _Provider()
    _patch_llm(monkeypatch, without_notes)
    response = await client.post(
        f"/api/notebooks/{notebook_id}/chat",
        headers=headers,
        json={"message": "在说什么？", "source_ids": [selected_id]},
    )
    assert response.status_code == 200, response.text
    assert without_notes.systems == [_SUBTITLE_ONLY_SYSTEM]

    with_notes = _Provider()
    _patch_llm(monkeypatch, with_notes)
    response = await client.post(
        f"/api/notebooks/{notebook_id}/chat",
        headers=headers,
        json={
            "message": "在说什么？",
            "source_ids": [selected_id],
            "note_ids": [note.id],
        },
    )
    assert response.status_code == 200, response.text
    assert with_notes.systems == [_NOTES_SYSTEM]
