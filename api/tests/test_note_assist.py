"""笔记选区帮写：流式返回，解读去掉引用编号，不写入对话。"""
from __future__ import annotations

import json

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.llm.config_service import LlmResolved
from app.models.notebook import Notebook, NotebookSource, Subtitle, SubtitleLine, Video
from app.models.user import User
from app.services.note_assist import CitePeeler


def test_cite_peeler_holds_a_split_marker():
    peeler = CitePeeler()
    assert peeler.push("看[") == "看"
    assert peeler.push("1]这里") == "这里"
    assert peeler.flush() == ""


def test_cite_peeler_drops_a_whole_marker():
    peeler = CitePeeler()
    assert peeler.push("财政[12]收缩") == "财政收缩"
    assert peeler.flush() == ""


class _Provider:
    def __init__(self, parts: list[str]) -> None:
        self.parts = parts
        self.prompts: list[str] = []
        self.systems: list[str | None] = []

    async def stream_chat(self, prompt, *, system=None, history=None, **kwargs):
        self.prompts.append(prompt)
        self.systems.append(system)
        for part in self.parts:
            yield part


def _patch_llm(monkeypatch, provider: _Provider) -> None:
    async def fake_llm(_session):
        return LlmResolved(
            provider="minimax",
            base_url="https://api.minimaxi.com/v1",
            api_key="sk-test",
            model_name="MiniMax-M3",
            params_json=None,
        )

    monkeypatch.setattr("app.services.note_assist.get_active_llm", fake_llm)
    monkeypatch.setattr("app.services.note_assist.make_provider", lambda **kwargs: provider)


async def _user(db_session, phone: str) -> tuple[User, str]:
    user = User(phone=phone, name=phone, role="user", status="active")
    user.set_password("userpw1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token, _ = create_access_token(user.id, role="user")
    return user, token


async def _notebook_with_line(db_session, user: User) -> tuple[int, int]:
    notebook = Notebook(owner_id=user.id, title="笔记", is_pinned=False, share_all=False)
    video = Video(
        owner_id=user.id,
        source_type="upload",
        status="ready",
        subtitle_status="ready",
        overview_status="pending",
        title="选中的片子",
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
    subtitle = Subtitle(video_id=video.id, source="asr", format="srt", line_count=1, version=1)
    db_session.add(subtitle)
    await db_session.commit()
    await db_session.refresh(subtitle)
    db_session.add(
        SubtitleLine(
            subtitle_id=subtitle.id,
            line_no=4,
            start_ms=0,
            end_ms=1000,
            text="财政在收缩",
        )
    )
    await db_session.commit()
    return notebook.id, video.id


def _events(raw: str) -> list[dict]:
    return [
        json.loads(line.removeprefix("data: "))
        for line in raw.splitlines()
        if line.startswith("data: ")
    ]


@pytest.mark.asyncio
async def test_explain_strips_citations_and_skips_chat(client: AsyncClient, db_session, monkeypatch):
    user, token = await _user(db_session, "13800000981")
    notebook_id, video_id = await _notebook_with_line(db_session, user)
    provider = _Provider(["整理足够长", "[1]", "。"])
    _patch_llm(monkeypatch, provider)
    headers = {"Authorization": f"Bearer {token}"}

    async with client.stream(
        "POST",
        f"/api/notebooks/{notebook_id}/notes/assist",
        headers=headers,
        json={
            "action": "explain",
            "selection": "整理时间足够长",
            "source_ids": [video_id],
        },
    ) as response:
        assert response.status_code == 200, await response.aread()
        raw = (await response.aread()).decode()

    events = _events(raw)
    text = "".join(event.get("t", "") for event in events if event["type"] == "token")
    assert "[1]" not in text
    assert "整理足够长" in text
    done = events[-1]
    assert done["type"] == "done"
    assert "[1]" not in done["text"]
    assert "不要使用" in (provider.systems[0] or "")
    assert "财政在收缩" in provider.prompts[0]
    assert "[1]" not in provider.prompts[0]
    history = await client.get(f"/api/notebooks/{notebook_id}/chat", headers=headers)
    assert history.json()["messages"] == []


@pytest.mark.asyncio
async def test_write_uses_instruction_and_rejects_blank_selection(
    client: AsyncClient, db_session, monkeypatch
):
    user, token = await _user(db_session, "13800000982")
    notebook = Notebook(owner_id=user.id, title="笔记", is_pinned=False, share_all=False)
    outsider = User(phone="13800000983", name="outsider", role="user", status="active")
    outsider.set_password("userpw1234")
    db_session.add_all([notebook, outsider])
    await db_session.commit()
    await db_session.refresh(notebook)
    await db_session.refresh(outsider)
    provider = _Provider(["写顺了"])
    _patch_llm(monkeypatch, provider)
    headers = {"Authorization": f"Bearer {token}"}
    other, _ = create_access_token(outsider.id, role="user")

    blank = await client.post(
        f"/api/notebooks/{notebook.id}/notes/assist",
        headers=headers,
        json={"action": "write", "selection": "   "},
    )
    assert blank.status_code == 400

    hidden = await client.post(
        f"/api/notebooks/{notebook.id}/notes/assist",
        headers={"Authorization": f"Bearer {other}"},
        json={"action": "write", "selection": "一段话"},
    )
    assert hidden.status_code == 404

    async with client.stream(
        "POST",
        f"/api/notebooks/{notebook.id}/notes/assist",
        headers=headers,
        json={"action": "write", "selection": "一段话", "instruction": "再短一点"},
    ) as response:
        assert response.status_code == 200, await response.aread()
        raw = (await response.aread()).decode()
    assert "再短一点" in provider.prompts[0]
    assert "一段话" in provider.prompts[0]
    done = _events(raw)[-1]
    assert done["text"] == "写顺了"
