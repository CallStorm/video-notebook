"""Tag CRUD, membership, and auto-organize apply."""
from __future__ import annotations

import pytest_asyncio

from app.core.security import create_access_token
from app.models.notebook import Notebook
from app.models.user import User


@pytest_asyncio.fixture
async def owner(db_session) -> User:
    user = User(phone="13800000901", name="TagOwner", role="user", status="active")
    user.set_password("userpw1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def owner_headers(owner) -> dict[str, str]:
    token, _ = create_access_token(owner.id, role=owner.role)
    return {"Authorization": f"Bearer {token}"}


async def test_create_list_patch_delete_tag(client, owner_headers):
    created = await client.post(
        "/api/tags",
        headers=owner_headers,
        json={"name": "  会议  ", "color": "#2F6B4F"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "会议"
    assert body["color"] == "#2F6B4F"
    assert body["notebook_count"] == 0

    listed = await client.get("/api/tags", headers=owner_headers)
    assert listed.status_code == 200
    assert any(row["id"] == body["id"] for row in listed.json())

    patched = await client.patch(
        f"/api/tags/{body['id']}",
        headers=owner_headers,
        json={"name": "开会", "color": "#3B82F6"},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "开会"
    assert patched.json()["color"] == "#3B82F6"

    blank = await client.post("/api/tags", headers=owner_headers, json={"name": "   "})
    assert blank.status_code == 400

    dup = await client.post("/api/tags", headers=owner_headers, json={"name": "开会"})
    assert dup.status_code == 400

    deleted = await client.delete(f"/api/tags/{body['id']}", headers=owner_headers)
    assert deleted.status_code == 204
    listed2 = await client.get("/api/tags", headers=owner_headers)
    assert all(row["id"] != body["id"] for row in listed2.json())


async def test_notebook_tag_membership(client, db_session, owner, owner_headers):
    a = Notebook(owner_id=owner.id, title="A", is_pinned=False, share_all=False)
    b = Notebook(owner_id=owner.id, title="B", is_pinned=False, share_all=False)
    db_session.add_all([a, b])
    await db_session.commit()
    await db_session.refresh(a)
    await db_session.refresh(b)

    t1 = (await client.post("/api/tags", headers=owner_headers, json={"name": "产品"})).json()
    t2 = (await client.post("/api/tags", headers=owner_headers, json={"name": "技术"})).json()

    put = await client.put(
        f"/api/notebooks/{a.id}/tags",
        headers=owner_headers,
        json={"tag_ids": [t1["id"], t2["id"]]},
    )
    assert put.status_code == 200
    assert set(put.json()["tag_ids"]) == {t1["id"], t2["id"]}
    assert {x["name"] for x in put.json()["tags"]} == {"产品", "技术"}

    got = await client.get(f"/api/notebooks/{a.id}/tags", headers=owner_headers)
    assert set(got.json()["tag_ids"]) == {t1["id"], t2["id"]}

    listed = await client.get("/api/notebooks?size=50", headers=owner_headers)
    assert listed.status_code == 200
    item_a = next(x for x in listed.json()["items"] if x["id"] == a.id)
    assert {t["name"] for t in item_a["tags"]} == {"产品", "技术"}

    filtered = await client.get(
        f"/api/notebooks?tag_id={t1['id']}&size=50", headers=owner_headers
    )
    assert filtered.status_code == 200
    ids = {x["id"] for x in filtered.json()["items"]}
    assert a.id in ids
    assert b.id not in ids

    # clear
    cleared = await client.put(
        f"/api/notebooks/{a.id}/tags",
        headers=owner_headers,
        json={"tag_ids": []},
    )
    assert cleared.json()["tag_ids"] == []


async def test_auto_organize_apply_covers_associations(
    client, db_session, owner, owner_headers
):
    a = Notebook(owner_id=owner.id, title="周会纪要", is_pinned=False, share_all=False)
    b = Notebook(owner_id=owner.id, title="产品路线图", is_pinned=False, share_all=False)
    db_session.add_all([a, b])
    await db_session.commit()
    await db_session.refresh(a)
    await db_session.refresh(b)

    old = (
        await client.post("/api/tags", headers=owner_headers, json={"name": "旧标签"})
    ).json()
    await client.put(
        f"/api/notebooks/{a.id}/tags",
        headers=owner_headers,
        json={"tag_ids": [old["id"]]},
    )

    applied = await client.post(
        "/api/tags/auto-organize/apply",
        headers=owner_headers,
        json={
            "tags": [
                {"temp_id": "t1", "name": "会议", "color": "#2F6B4F"},
                {"temp_id": "t2", "name": "产品", "color": "#3B82F6"},
            ],
            "assignments": [
                {"notebook_id": a.id, "tag_temp_ids": ["t1"]},
                {"notebook_id": b.id, "tag_temp_ids": ["t2", "t1"]},
            ],
        },
    )
    assert applied.status_code == 200
    names = {t["name"] for t in applied.json()["tags"]}
    assert names == {"会议", "产品"}

    # old tag was linked then orphaned by cover → deleted (not left as empty)
    all_tags = (await client.get("/api/tags", headers=owner_headers)).json()
    assert all(t["id"] != old["id"] for t in all_tags)
    assert {"会议", "产品"}.issubset({t["name"] for t in all_tags})
    assert all(t["notebook_count"] >= 1 for t in all_tags)

    a_tags = (await client.get(f"/api/notebooks/{a.id}/tags", headers=owner_headers)).json()
    b_tags = (await client.get(f"/api/notebooks/{b.id}/tags", headers=owner_headers)).json()
    assert {t["name"] for t in a_tags["tags"]} == {"会议"}
    assert {t["name"] for t in b_tags["tags"]} == {"会议", "产品"}
    assert old["id"] not in a_tags["tag_ids"]


def test_normalize_preview_drops_unused_tags():
    """LLM may invent tags that never get assigned; preview must hide them."""
    from app.services.tags import _normalize_preview_plan

    notebooks = [
        {"id": 1, "title": "A", "description": None},
        {"id": 2, "title": "B", "description": None},
    ]
    raw = {
        "tags": [
            {"name": "有关联"},
            {"name": "空标签"},
            {"name": "投资理财"},
        ],
        "assignments": [
            {"notebook_id": 1, "tag_names": ["有关联"]},
            {"notebook_id": 2, "tag_names": ["有关联"]},
        ],
    }
    tags, assignments = _normalize_preview_plan(raw, notebooks)
    names = {t["name"] for t in tags}
    assert names == {"有关联"}
    assert all(a["tag_temp_ids"] for a in assignments)
    used = {tid for a in assignments for tid in a["tag_temp_ids"]}
    assert {t["temp_id"] for t in tags} == used


async def test_auto_organize_apply_skips_unused_and_sweeps_empty(
    client, db_session, owner, owner_headers
):
    """Unused plan tags are not created; confirm sweeps leftover empty tags."""
    a = Notebook(owner_id=owner.id, title="笔记A", is_pinned=False, share_all=False)
    db_session.add(a)
    await db_session.commit()
    await db_session.refresh(a)

    manual = (
        await client.post(
            "/api/tags", headers=owner_headers, json={"name": "手建空标签"}
        )
    ).json()
    assert manual["notebook_count"] == 0

    applied = await client.post(
        "/api/tags/auto-organize/apply",
        headers=owner_headers,
        json={
            "tags": [
                {"temp_id": "t1", "name": "在用", "color": "#2F6B4F"},
                {"temp_id": "t2", "name": "方案空标签", "color": "#EF4444"},
            ],
            "assignments": [
                {"notebook_id": a.id, "tag_temp_ids": ["t1"]},
            ],
        },
    )
    assert applied.status_code == 200
    returned = {t["name"] for t in applied.json()["tags"]}
    assert returned == {"在用"}

    all_tags = (await client.get("/api/tags", headers=owner_headers)).json()
    names = {t["name"]: t["notebook_count"] for t in all_tags}
    assert "方案空标签" not in names
    assert "手建空标签" not in names  # swept on confirm
    assert names.get("在用", 0) >= 1
    assert all(c >= 1 for c in names.values()), names


async def test_auto_organize_apply_twice_does_not_accumulate_empty(
    client, db_session, owner, owner_headers
):
    """Second cover with new names must not leave previous plan tags as empties."""
    a = Notebook(owner_id=owner.id, title="笔记A", is_pinned=False, share_all=False)
    b = Notebook(owner_id=owner.id, title="笔记B", is_pinned=False, share_all=False)
    db_session.add_all([a, b])
    await db_session.commit()
    await db_session.refresh(a)
    await db_session.refresh(b)

    first = await client.post(
        "/api/tags/auto-organize/apply",
        headers=owner_headers,
        json={
            "tags": [
                {"temp_id": "t1", "name": "投资理财", "color": "#2F6B4F"},
                {"temp_id": "t2", "name": "人工智能", "color": "#EF4444"},
            ],
            "assignments": [
                {"notebook_id": a.id, "tag_temp_ids": ["t1"]},
                {"notebook_id": b.id, "tag_temp_ids": ["t2"]},
            ],
        },
    )
    assert first.status_code == 200

    second = await client.post(
        "/api/tags/auto-organize/apply",
        headers=owner_headers,
        json={
            "tags": [
                {"temp_id": "u1", "name": "趋势交易", "color": "#3B82F6"},
                {"temp_id": "u2", "name": "AI基础", "color": "#8B5CF6"},
                {"temp_id": "u3", "name": "未使用空名", "color": "#F59E0B"},
            ],
            "assignments": [
                {"notebook_id": a.id, "tag_temp_ids": ["u1"]},
                {"notebook_id": b.id, "tag_temp_ids": ["u2"]},
            ],
        },
    )
    assert second.status_code == 200

    all_tags = (await client.get("/api/tags", headers=owner_headers)).json()
    names = {t["name"] for t in all_tags}
    assert "投资理财" not in names
    assert "人工智能" not in names
    assert "未使用空名" not in names
    assert {"趋势交易", "AI基础"}.issubset(names)
    assert all(t["notebook_count"] >= 1 for t in all_tags)
