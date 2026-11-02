"""结论评判只对照底稿要点，不改写用户结论。"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.llm.config_service import LlmResolved
from app.models.knowledge_draft import NotebookKnowledgeDraft
from app.models.notebook import Notebook
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


async def _draft(db_session) -> tuple[str, int]:
    user = User(phone="13800000922", name="owner", role="user", status="active")
    user.set_password("userpw1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    notebook = Notebook(owner_id=user.id, title="交易", is_pinned=False, share_all=False)
    db_session.add(notebook)
    await db_session.commit()
    await db_session.refresh(notebook)
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
                    "evidence": "在稳定趋势中等待价格回撤至均线附近",
                    "example": "像顺势游泳时利用浪谷调整",
                    "checked": True,
                }
            ],
            "takeaways": [{"id": "t1", "text": "不要出现在评判材料里", "checked": True}],
            "open_questions": ["不要出现在评判材料里"],
            "conclusions": ["回撤到均线就必须进场"],
        },
        source_video_ids=[],
        source_note_ids=[],
    )
    db_session.add(row)
    await db_session.commit()
    token, _ = create_access_token(user.id, role="user")
    return token, notebook.id


@pytest.mark.asyncio
async def test_review_judges_against_points_and_keeps_the_conclusion(
    client: AsyncClient, db_session, monkeypatch
):
    token, notebook_id = await _draft(db_session)
    provider = _Provider(
        '{"verdict":"broader","evidence":"在稳定趋势中等待价格回撤至均线附近","gap":"原片只说到附近，没有说必须进场"}'
    )
    _patch_llm(monkeypatch, provider)
    response = await client.post(
        f"/api/notebooks/{notebook_id}/knowledge-draft/review",
        headers={"Authorization": f"Bearer {token}"},
        json={"conclusion": "回撤到均线就必须进场"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["verdict"] == "broader"
    assert "均线附近" in body["evidence"]
    assert "必须进场" in body["gap"]
    prompt = provider.prompts[0]
    assert "在稳定趋势中等待价格回撤至均线附近" in prompt
    assert "不要出现在评判材料里" not in prompt
    assert "回撤到均线就必须进场" in prompt
    got = await client.get(
        f"/api/notebooks/{notebook_id}/knowledge-draft",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert got.json()["conclusions"] == ["回撤到均线就必须进场"]
