"""发现页关键词搜索：scope=all|mine|shared，不泄漏他人私有本。"""
from __future__ import annotations

from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.notebook import Notebook, NotebookSource, Video
from app.models.user import User


async def _user(db_session, phone: str, name: str) -> tuple[User, str]:
    u = User(phone=phone, name=name, role="user", status="active")
    u.set_password("userpw1234")
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    token, _ = create_access_token(u.id, role="user")
    return u, token


async def _nb(
    db_session,
    owner: User,
    *,
    title: str,
    description: str | None = None,
    share_all: bool = False,
    overview: str | None = None,
    with_source: bool = False,
) -> Notebook:
    nb = Notebook(
        owner_id=owner.id,
        title=title,
        description=description,
        is_pinned=False,
        share_all=share_all,
    )
    db_session.add(nb)
    await db_session.commit()
    await db_session.refresh(nb)
    if overview is not None or with_source:
        video = Video(
            owner_id=owner.id,
            source_type="upload",
            status="ready",
            subtitle_status="pending",
            overview_status="ready" if overview is not None else "pending",
            overview_text=overview,
            title="片源",
        )
        db_session.add(video)
        await db_session.commit()
        await db_session.refresh(video)
        db_session.add(
            NotebookSource(
                notebook_id=nb.id,
                video_id=video.id,
                sort=0,
                selected_for_chat=True,
            )
        )
        await db_session.commit()
    return nb


async def test_discover_scopes_and_keyword(client: AsyncClient, db_session):
    owner, t1 = await _user(db_session, "13800001001", "甲")
    viewer, t2 = await _user(db_session, "13800001002", "乙")
    h1 = {"Authorization": f"Bearer {t1}"}
    h2 = {"Authorization": f"Bearer {t2}"}

    mine_private = await _nb(
        db_session, viewer, title="我的减脂计划", description="私有饮食笔记", with_source=True
    )
    mine_shared = await _nb(
        db_session,
        viewer,
        title="我公开的训练",
        description="力量训练",
        share_all=True,
        with_source=True,
    )
    other_shared = await _nb(
        db_session,
        owner,
        title="公开减脂本",
        description="分享用",
        share_all=True,
        overview="讲解如何快速减脂与饮食安排",
    )
    other_private = await _nb(
        db_session,
        owner,
        title="私有减脂秘密",
        description="绝不能搜到",
        overview="减脂关键词在私有概览",
    )
    other_desc = await _nb(
        db_session,
        owner,
        title="运动合集",
        description="关于减脂的公开描述",
        share_all=True,
        with_source=True,
    )

    # 空 q + shared：仅他人公开
    r = await client.get("/api/notebooks/discover", headers=h2, params={"scope": "shared"})
    assert r.status_code == 200, r.text
    body = r.json()
    ids = {item["id"] for item in body["items"]}
    assert other_shared.id in ids
    assert other_desc.id in ids
    assert mine_private.id not in ids
    assert mine_shared.id not in ids  # shared scope 不含自己的
    assert other_private.id not in ids

    # 空 q + mine：仅自己的
    r = await client.get("/api/notebooks/discover", headers=h2, params={"scope": "mine"})
    ids = {item["id"] for item in r.json()["items"]}
    assert mine_private.id in ids and mine_shared.id in ids
    assert other_shared.id not in ids and other_private.id not in ids

    # 空 q + all：自己的 + 他人公开
    r = await client.get("/api/notebooks/discover", headers=h2, params={"scope": "all"})
    ids = {item["id"] for item in r.json()["items"]}
    assert mine_private.id in ids and other_shared.id in ids
    assert other_private.id not in ids

    # 关键词：标题命中优先
    r = await client.get(
        "/api/notebooks/discover",
        headers=h2,
        params={"scope": "all", "q": "减脂"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    ids = [item["id"] for item in body["items"]]
    assert other_private.id not in ids
    assert mine_private.id in ids
    assert other_shared.id in ids
    assert other_desc.id in ids
    # 标题命中排在描述/概览前：我的减脂计划、公开减脂本 应靠前
    title_hits = [item for item in body["items"] if item["match_hint"] == "命中标题"]
    assert any(item["id"] == mine_private.id for item in title_hits)
    assert any(item["id"] == other_shared.id for item in title_hits)
    desc_or_overview = [
        item
        for item in body["items"]
        if item["id"] == other_desc.id or item["id"] == other_shared.id
    ]
    assert any(item["match_hint"] in {"命中标题", "命中描述", "命中概览"} for item in desc_or_overview)

    # 仅 shared 搜「减脂」：不含自己的私有本
    r = await client.get(
        "/api/notebooks/discover",
        headers=h2,
        params={"scope": "shared", "q": "减脂"},
    )
    ids = {item["id"] for item in r.json()["items"]}
    assert mine_private.id not in ids
    assert other_private.id not in ids
    assert other_shared.id in ids

    # 概览命中
    r = await client.get(
        "/api/notebooks/discover",
        headers=h2,
        params={"scope": "shared", "q": "饮食安排"},
    )
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == other_shared.id
    assert items[0]["match_hint"] == "命中概览"


async def test_discover_never_leaks_private(client: AsyncClient, db_session):
    owner, _t1 = await _user(db_session, "13800001011", "主")
    _, t2 = await _user(db_session, "13800001012", "客")
    h2 = {"Authorization": f"Bearer {t2}"}
    secret = await _nb(
        db_session,
        owner,
        title="绝密关键字XYZABC",
        description="绝密关键字XYZABC",
        overview="绝密关键字XYZABC",
        share_all=False,
    )
    for scope in ("all", "mine", "shared"):
        r = await client.get(
            "/api/notebooks/discover",
            headers=h2,
            params={"scope": scope, "q": "XYZABC"},
        )
        assert r.status_code == 200
        assert all(item["id"] != secret.id for item in r.json()["items"])


async def test_discover_semantic_ranks_and_scopes(client: AsyncClient, db_session, monkeypatch):
    """语义模式：按 mock 分数排序，且不泄漏私有本。"""
    from app.llm.config_service import EmbeddingResolved
    from app.vector.store import VectorHit

    owner, _t1 = await _user(db_session, "13800002001", "甲")
    viewer, t2 = await _user(db_session, "13800002002", "乙")
    h2 = {"Authorization": f"Bearer {t2}"}

    mine = await _nb(
        db_session, viewer, title="我的饮食本", description="私有", with_source=True
    )
    shared = await _nb(
        db_session,
        owner,
        title="公开健康指南",
        description="公开",
        share_all=True,
        with_source=True,
    )
    secret = await _nb(
        db_session,
        owner,
        title="私有秘密本",
        description="不该出现",
        share_all=False,
        with_source=True,
    )

    async def fake_embed(session):
        return EmbeddingResolved(
            provider="openai",
            base_url="http://embed.test/v1",
            api_key="sk-test",
            model_name="fake-emb",
            params_json=None,
        )

    async def fake_embed_query(_resolved, text: str):
        assert "减脂" in text or text
        return [0.1, 0.2, 0.3]

    class FakeStore:
        async def search(self, vector, *, limit=20, notebook_ids=None, score_threshold=None):
            assert vector == [0.1, 0.2, 0.3]
            ids = set(notebook_ids or [])
            # secret 即使被索引也不该在候选里
            assert secret.id not in ids
            hits = []
            if shared.id in ids:
                hits.append(VectorHit(notebook_id=shared.id, score=0.91, payload={}))
            if mine.id in ids:
                hits.append(VectorHit(notebook_id=mine.id, score=0.77, payload={}))
            if secret.id in ids:
                hits.append(VectorHit(notebook_id=secret.id, score=0.99, payload={}))
            hits.sort(key=lambda h: h.score, reverse=True)
            if score_threshold is not None:
                hits = [h for h in hits if h.score >= float(score_threshold)]
            return hits[:limit]

    def fake_make_store(**kwargs):
        return FakeStore()

    class FakeSettings:
        vector_backend = "qdrant"
        qdrant_url = "http://127.0.0.1:6333"
        qdrant_collection = "notebooks"
        qdrant_api_key = None

    async def fake_settings_row(session):
        return FakeSettings()

    monkeypatch.setattr(
        "app.llm.config_service.get_active_embedding", fake_embed
    )
    # discover imports inside function — patch module paths used there
    monkeypatch.setattr(
        "app.services.notebooks.get_active_embedding", fake_embed, raising=False
    )
    monkeypatch.setattr(
        "app.vector.embeddings.embed_query", fake_embed_query
    )
    monkeypatch.setattr(
        "app.vector.store.make_vector_store", fake_make_store
    )
    monkeypatch.setattr(
        "app.services.vector_settings.get_vector_settings_row", fake_settings_row
    )

    # 需要直接 patch 在 notebooks service 内部延迟 import 的符号：
    # _discover_semantic 里 from app.llm... import get_active_embedding
    # 所以 patch 源模块即可（函数内 from 会拿到 monkeypatched 对象）
    import app.llm.config_service as cfg
    import app.vector.embeddings as emb
    import app.vector.store as store_mod
    import app.services.vector_settings as vs

    monkeypatch.setattr(cfg, "get_active_embedding", fake_embed)
    monkeypatch.setattr(emb, "embed_query", fake_embed_query)
    monkeypatch.setattr(store_mod, "make_vector_store", fake_make_store)
    monkeypatch.setattr(vs, "get_vector_settings_row", fake_settings_row)

    r = await client.get(
        "/api/notebooks/discover",
        headers=h2,
        params={"scope": "all", "mode": "semantic", "q": "怎么快速减脂"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    ids = [item["id"] for item in body["items"]]
    assert secret.id not in ids
    assert shared.id in ids and mine.id in ids
    # 分数高的 shared 排前
    assert ids.index(shared.id) < ids.index(mine.id)
    hints = {item["id"]: item["match_hint"] for item in body["items"]}
    assert hints[shared.id] and "语义相近" in hints[shared.id]

    # shared scope：不含自己的本
    r = await client.get(
        "/api/notebooks/discover",
        headers=h2,
        params={"scope": "shared", "mode": "semantic", "q": "减脂"},
    )
    ids = {item["id"] for item in r.json()["items"]}
    assert shared.id in ids
    assert mine.id not in ids
    assert secret.id not in ids


async def test_discover_semantic_requires_embedding(client: AsyncClient, db_session, monkeypatch):
    viewer, t2 = await _user(db_session, "13800002011", "乙")
    h2 = {"Authorization": f"Bearer {t2}"}
    await _nb(db_session, viewer, title="本", description="d", with_source=True)

    from app.core.errors import NotFoundError

    async def boom(session):
        raise NotFoundError("role=embedding 没有默认模型")

    import app.llm.config_service as cfg

    monkeypatch.setattr(cfg, "get_active_embedding", boom)

    r = await client.get(
        "/api/notebooks/discover",
        headers=h2,
        params={"scope": "mine", "mode": "semantic", "q": "测试"},
    )
    assert r.status_code == 503, r.text
    assert "向量模型" in r.json()["message"]


async def test_discover_semantic_empty_q_browses(client: AsyncClient, db_session):
    """语义模式空查询退回浏览，不打向量。"""
    viewer, t2 = await _user(db_session, "13800002021", "乙")
    h2 = {"Authorization": f"Bearer {t2}"}
    nb = await _nb(db_session, viewer, title="浏览本", description="x")
    r = await client.get(
        "/api/notebooks/discover",
        headers=h2,
        params={"scope": "mine", "mode": "semantic"},
    )
    assert r.status_code == 200, r.text
    ids = {item["id"] for item in r.json()["items"]}
    assert nb.id in ids


async def test_discover_search_excludes_empty_shells(client: AsyncClient, db_session):
    """有查询时，0 来源空壳不出现在关键词结果里。"""
    viewer, t2 = await _user(db_session, "13800003001", "乙")
    h2 = {"Authorization": f"Bearer {t2}"}
    empty = await _nb(db_session, viewer, title="减脂空壳", description="无来源")
    filled = await _nb(
        db_session,
        viewer,
        title="减脂实本",
        description="有来源",
        with_source=True,
    )
    r = await client.get(
        "/api/notebooks/discover",
        headers=h2,
        params={"scope": "mine", "q": "减脂"},
    )
    assert r.status_code == 200, r.text
    ids = {item["id"] for item in r.json()["items"]}
    assert filled.id in ids
    assert empty.id not in ids


async def test_discover_semantic_min_score_and_empty(client: AsyncClient, db_session, monkeypatch):
    """语义：低分丢弃；0 来源不在候选。"""
    from app.llm.config_service import EmbeddingResolved
    from app.vector.store import VectorHit

    viewer, t2 = await _user(db_session, "13800003011", "乙")
    h2 = {"Authorization": f"Bearer {t2}"}
    empty = await _nb(db_session, viewer, title="健身", description="空")
    weak = await _nb(
        db_session, viewer, title="中国经济", description="弱相关", with_source=True
    )
    strong = await _nb(
        db_session, viewer, title="如何快速减脂", description="强相关", with_source=True
    )

    async def fake_embed(session):
        return EmbeddingResolved(
            provider="openai",
            base_url="http://embed.test/v1",
            api_key="sk-test",
            model_name="fake-emb",
            params_json=None,
        )

    async def fake_embed_query(_resolved, text: str):
        return [0.1, 0.2, 0.3]

    class FakeStore:
        async def search(self, vector, *, limit=20, notebook_ids=None, score_threshold=None):
            ids = set(notebook_ids or [])
            assert empty.id not in ids  # 空壳不应进候选
            hits = []
            if strong.id in ids:
                hits.append(VectorHit(notebook_id=strong.id, score=0.63, payload={}))
            if weak.id in ids:
                hits.append(VectorHit(notebook_id=weak.id, score=0.40, payload={}))
            if empty.id in ids:
                hits.append(VectorHit(notebook_id=empty.id, score=0.55, payload={}))
            hits.sort(key=lambda h: h.score, reverse=True)
            if score_threshold is not None:
                hits = [h for h in hits if h.score >= float(score_threshold)]
            return hits[:limit]

    def fake_make_store(**kwargs):
        return FakeStore()

    class FakeSettings:
        vector_backend = "qdrant"
        qdrant_url = "http://127.0.0.1:6333"
        qdrant_collection = "notebooks"
        qdrant_api_key = None

    async def fake_settings_row(session):
        return FakeSettings()

    import app.llm.config_service as cfg
    import app.vector.embeddings as emb
    import app.vector.store as store_mod
    import app.services.vector_settings as vs

    monkeypatch.setattr(cfg, "get_active_embedding", fake_embed)
    monkeypatch.setattr(emb, "embed_query", fake_embed_query)
    monkeypatch.setattr(store_mod, "make_vector_store", fake_make_store)
    monkeypatch.setattr(vs, "get_vector_settings_row", fake_settings_row)

    # default threshold 0.55: weak 0.40 dropped, strong kept
    r = await client.get(
        "/api/notebooks/discover",
        headers=h2,
        params={"scope": "mine", "mode": "semantic", "q": "如何减肥"},
    )
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    ids = [item["id"] for item in items]
    assert strong.id in ids
    assert weak.id not in ids  # 0.40 < 0.55
    assert empty.id not in ids
    assert items[0]["id"] == strong.id
    assert "63%" in (items[0]["match_hint"] or "")

    # lower min_score=0.35 keeps weak hit
    r = await client.get(
        "/api/notebooks/discover",
        headers=h2,
        params={
            "scope": "mine",
            "mode": "semantic",
            "q": "如何减肥",
            "min_score": 0.35,
        },
    )
    assert r.status_code == 200, r.text
    ids = {item["id"] for item in r.json()["items"]}
    assert strong.id in ids and weak.id in ids
    assert empty.id not in ids

    # higher min_score=0.70 drops strong 0.63 too
    r = await client.get(
        "/api/notebooks/discover",
        headers=h2,
        params={
            "scope": "mine",
            "mode": "semantic",
            "q": "如何减肥",
            "min_score": 0.70,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["items"] == []

