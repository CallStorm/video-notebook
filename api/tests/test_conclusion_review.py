"""结论核对由模型对照笔记本字幕给出意见，不改写结论。"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import create_access_token
from app.llm.config_service import LlmResolved
from app.models.knowledge_draft import NotebookKnowledgeDraft
from app.models.notebook import Notebook, NotebookSource, Subtitle, SubtitleLine, Video
from app.models.user import User


class _Provider:
    def __init__(self, text: str) -> None:
        self.text = text
        self.prompts: list[str] = []
        self.systems: list[str | None] = []

    async def complete(self, prompt, *, system=None, **kwargs):
        self.prompts.append(prompt)
        self.systems.append(system)
        return self.text


def _patch_llm(monkeypatch, provider: _Provider) -> None:
    async def fake_llm(_session):
        return LlmResolved(
            provider="minimax",
            base_url="https://api.minimaxi.com/v1",
            api_key="sk-test",
            model_name="MiniMax-M3",
            params_json=None,
        )

    monkeypatch.setattr("app.services.knowledge_draft.get_active_llm", fake_llm)
    monkeypatch.setattr("app.services.knowledge_draft.make_provider", lambda **kwargs: provider)


async def _draft(db_session) -> tuple[str, int, int]:
    user = User(phone="13800000922", name="owner", role="user", status="active")
    user.set_password("userpw1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    notebook = Notebook(owner_id=user.id, title="交易", is_pinned=False, share_all=False)
    video = Video(
        owner_id=user.id,
        source_type="upload",
        status="ready",
        subtitle_status="ready",
        overview_status="pending",
        title="均线",
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
    subtitle = Subtitle(video_id=video.id, source="asr", format="srt", line_count=2, version=1)
    db_session.add(subtitle)
    await db_session.commit()
    await db_session.refresh(subtitle)
    db_session.add_all(
        [
            SubtitleLine(
                subtitle_id=subtitle.id,
                line_no=2,
                start_ms=40_000,
                end_ms=44_000,
                text="没有说必须马上进场",
            ),
            SubtitleLine(
                subtitle_id=subtitle.id,
                line_no=1,
                start_ms=12_000,
                end_ms=16_000,
                text="在稳定趋势中等待价格回撤至均线附近",
            ),
        ]
    )
    row = NotebookKnowledgeDraft(
        notebook_id=notebook.id,
        owner_id=user.id,
        status="ready",
        conclusion="回撤到均线就必须进场",
        content_json={
            "theme": "顺势回撤",
            "concepts": [],
            "points": [
                {
                    "id": "p1",
                    "text": "等待价格回撤到均线附近",
                    "evidence": "要点里的原句不该进核对",
                    "example": "像顺势游泳时利用浪谷调整",
                    "checked": True,
                }
            ],
            "takeaways": [{"id": "t1", "text": "不要出现在核对材料里", "checked": True}],
            "open_questions": ["不要出现在核对材料里"],
            "conclusions": ["回撤到均线就必须进场"],
        },
        source_video_ids=[video.id],
        source_note_ids=[],
    )
    db_session.add(row)
    await db_session.commit()
    token, _ = create_access_token(user.id, role="user")
    return token, notebook.id, video.id


@pytest.mark.asyncio
async def test_review_compares_the_conclusion_with_notebook_subtitles(
    client: AsyncClient, db_session, monkeypatch
):
    token, notebook_id, video_id = await _draft(db_session)
    provider = _Provider(
        '{"verdict":"partial","gap":"字幕只说到附近，没有说必须进场",'
        f'"lines":[{{"video_id":{video_id},"line_no":2}},{{"video_id":{video_id},"line_no":1}},'
        f'{{"video_id":{video_id},"line_no":99}}]}}'
    )
    _patch_llm(monkeypatch, provider)
    response = await client.post(
        f"/api/notebooks/{notebook_id}/knowledge-draft/review",
        headers={"Authorization": f"Bearer {token}"},
        json={"conclusion": "回撤到均线就必须进场"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["verdict"] == "partial"
    assert "必须进场" in body["gap"]
    assert [line["line_no"] for line in body["lines"]] == [1, 2]
    assert body["lines"][0]["text"] == "在稳定趋势中等待价格回撤至均线附近"
    prompt = provider.prompts[0]
    assert prompt.index("在稳定趋势中等待价格回撤至均线附近") < prompt.index("没有说必须马上进场")
    assert "回撤到均线就必须进场" in prompt
    assert "要点里的原句不该进核对" not in prompt
    assert "不要出现在核对材料里" not in prompt
    got = await client.get(
        f"/api/notebooks/{notebook_id}/knowledge-draft",
        headers={"Authorization": f"Bearer {token}"},
    )
    draft = got.json()
    assert draft["conclusions"] == ["回撤到均线就必须进场"]
    assert draft["conclusion_checks"][0]["verdict"] == "partial"
    assert draft["conclusion_checks"][0]["text"] == "回撤到均线就必须进场"
    assert len(draft["conclusion_checks"][0]["lines"]) == 2


@pytest.mark.asyncio
async def test_review_ignores_subtitles_outside_the_notebook(
    client: AsyncClient, db_session, monkeypatch
):
    token, notebook_id, _video_id = await _draft(db_session)
    user_id = (
        await db_session.execute(select(User.id).where(User.phone == "13800000922"))
    ).scalar_one()
    other = Video(
        owner_id=user_id,
        source_type="upload",
        status="ready",
        subtitle_status="ready",
        overview_status="pending",
        title="别的片子",
    )
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)
    subtitle = Subtitle(video_id=other.id, source="asr", format="srt", line_count=1, version=1)
    db_session.add(subtitle)
    await db_session.commit()
    await db_session.refresh(subtitle)
    db_session.add(
        SubtitleLine(
            subtitle_id=subtitle.id,
            line_no=1,
            start_ms=0,
            end_ms=1000,
            text="这句不在笔记本里",
        )
    )
    await db_session.commit()
    provider = _Provider(
        '{"verdict":"supported","gap":"字幕里有回撤到均线附近",'
        f'"lines":[{{"video_id":{other.id},"line_no":1}}]}}'
    )
    _patch_llm(monkeypatch, provider)
    response = await client.post(
        f"/api/notebooks/{notebook_id}/knowledge-draft/review",
        headers={"Authorization": f"Bearer {token}"},
        json={"conclusion": "回撤到均线就必须进场"},
    )
    assert response.status_code == 200, response.text
    assert "这句不在笔记本里" not in provider.prompts[0]
    assert response.json()["lines"] == []


@pytest.mark.asyncio
async def test_editing_the_conclusion_drops_the_check(client: AsyncClient, db_session, monkeypatch):
    token, notebook_id, video_id = await _draft(db_session)
    _patch_llm(monkeypatch, _Provider('{"verdict":"supported","gap":""}'))
    headers = {"Authorization": f"Bearer {token}"}
    reviewed = await client.post(
        f"/api/notebooks/{notebook_id}/knowledge-draft/review",
        headers=headers,
        json={"conclusion": "回撤到均线就必须进场"},
    )
    assert reviewed.status_code == 200, reviewed.text
    changed = await client.patch(
        f"/api/notebooks/{notebook_id}/knowledge-draft",
        headers=headers,
        json={"conclusions": ["回撤到均线再观察"]},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["conclusions"] == ["回撤到均线再观察"]
    assert changed.json()["conclusion_checks"] == []
