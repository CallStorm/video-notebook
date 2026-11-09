"""分段索引：只嵌入有变化的段，搜索结果按笔记本取最高分。"""
from __future__ import annotations

import pytest

from app.llm.config_service import EmbeddingResolved
from app.models.notebook import Note, Notebook
from app.models.user import User
from app.vector.store import hits_from_search_groups


def test_search_groups_keeps_best_chunk_per_notebook():
    hits = hits_from_search_groups(
        {
            "result": {
                "groups": [
                    {
                        "id": 16,
                        "hits": [
                            {
                                "id": "chunk-a",
                                "score": 0.91,
                                "payload": {"notebook_id": 16, "part": "subtitles"},
                            }
                        ],
                    },
                    {
                        "id": 7,
                        "hits": [
                            {
                                "id": "chunk-b",
                                "score": 0.4,
                                "payload": {"notebook_id": 7, "part": "notes"},
                            },
                            {
                                "id": "chunk-c",
                                "score": 0.62,
                                "payload": {"notebook_id": 7, "part": "draft"},
                            },
                        ],
                    },
                ]
            }
        }
    )
    assert [hit.notebook_id for hit in hits] == [16, 7]
    assert hits[0].payload["part"] == "subtitles"
    assert hits[1].score == 0.62
    assert hits[1].payload["part"] == "draft"


@pytest.mark.asyncio
async def test_reindex_embeds_only_the_changed_chunk(db_session, monkeypatch):
    user = User(phone="13800000941", name="owner", role="user", status="active")
    user.set_password("userpw1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    notebook = Notebook(owner_id=user.id, title="分段索引", description=None, share_all=False)
    db_session.add(notebook)
    await db_session.commit()
    await db_session.refresh(notebook)
    note = Note(
        notebook_id=notebook.id,
        author_id=user.id,
        title="摘录",
        content_text="原来的笔记",
        selected_for_chat=False,
    )
    db_session.add(note)
    await db_session.commit()

    embedded: list[list[str]] = []

    async def fake_embed(_resolved, texts):
        embedded.append(list(texts))
        return [[0.1, 0.2, 0.3, 0.4] for _ in texts]

    async def fake_model(_session):
        return EmbeddingResolved(
            provider="openai",
            base_url="http://embed.test/v1",
            api_key="sk-test",
            model_name="fake-emb",
            params_json=None,
        )

    class Store:
        def __init__(self):
            self.points: dict[str, dict] = {}

        async def ensure_collection(self, dim: int) -> None:
            self.dim = dim

        async def scroll_notebook(self, notebook_id: int):
            return [
                (point_id, {**point.payload, "notebook_id": point.notebook_id})
                for point_id, point in self.points.items()
                if point.notebook_id == notebook_id
            ]

        async def upsert_many(self, points) -> None:
            for point in points:
                self.points[str(point.point_id)] = point

        async def delete_points(self, point_ids) -> None:
            for point_id in point_ids:
                self.points.pop(str(point_id), None)

        async def set_payload(self, notebook_id: int, payload: dict) -> None:
            for point in self.points.values():
                if point.notebook_id == notebook_id:
                    point.payload.update(payload)

    store = Store()
    monkeypatch.setattr("app.vector.indexer.embed_texts", fake_embed)
    monkeypatch.setattr("app.vector.indexer.make_vector_store", lambda **_kwargs: store)
    monkeypatch.setattr("app.vector.indexer.get_active_embedding", fake_model)

    from app.vector.indexer import index_notebook

    state = await index_notebook(db_session, notebook.id)
    assert state.status == "ready"
    assert len(embedded) == 1
    assert len(embedded[0]) == 2
    assert any("原来的笔记" in text for text in embedded[0])
    assert all(str(point_id) != str(notebook.id) for point_id in store.points)

    embedded.clear()
    state = await index_notebook(db_session, notebook.id)
    assert state.status == "ready"
    assert embedded == []

    note.content_text = "改过的笔记"
    await db_session.commit()
    state = await index_notebook(db_session, notebook.id)
    assert state.status == "ready"
    assert len(embedded) == 1
    assert len(embedded[0]) == 1
    assert "改过的笔记" in embedded[0][0]
    assert "原来的笔记" not in embedded[0][0]
    assert len(store.points) == 2
