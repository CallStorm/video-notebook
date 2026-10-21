"""Admin vector settings + notebook reindex enqueue."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.notebook import Notebook
from app.models.user import User


async def _admin(db_session) -> tuple[User, str]:
    u = User(phone="13800000121", name="admin-vec", role="admin", status="active")
    u.set_password("adminpw1234")
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    token, _ = create_access_token(u.id, role="admin")
    return u, token


@pytest.mark.asyncio
async def test_vector_settings_get_put(client: AsyncClient, db_session):
    _u, token = await _admin(db_session)
    h = {"Authorization": f"Bearer {token}"}

    r = await client.get("/api/admin/vector-settings", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["vector_backend"] == "qdrant"
    assert body["qdrant_collection"] == "notebooks"
    assert body["index_title"] is True
    assert body["index_overview"] is True
    assert body["index_subtitles"] is False

    r2 = await client.put(
        "/api/admin/vector-settings",
        headers=h,
        json={
            "vector_backend": "qdrant",
            "qdrant_url": "http://127.0.0.1:6333",
            "qdrant_api_key": "secret-key",
            "clear_qdrant_api_key": False,
            "qdrant_collection": "notebooks_v2",
            "index_title": True,
            "index_description": False,
            "index_overview": True,
            "index_subtitles": True,
            "index_notes": False,
        },
    )
    assert r2.status_code == 200, r2.text
    got = r2.json()
    assert got["qdrant_collection"] == "notebooks_v2"
    assert got["index_description"] is False
    assert got["index_subtitles"] is True
    assert got["qdrant_api_key_set"] is True
    assert got["qdrant_api_key"] is None  # 不明文回传


@pytest.mark.asyncio
async def test_notebook_reindex_endpoint(client: AsyncClient, db_session):
    u, token = await _admin(db_session)
    h = {"Authorization": f"Bearer {token}"}
    nb = Notebook(owner_id=u.id, title="向量本", description="desc", share_all=False)
    db_session.add(nb)
    await db_session.commit()
    await db_session.refresh(nb)

    r = await client.get(f"/api/notebooks/{nb.id}/index", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending"

    r2 = await client.post(f"/api/notebooks/{nb.id}/reindex", headers=h)
    assert r2.status_code == 200, r2.text
    assert r2.json()["notebook_id"] == nb.id
    assert r2.json()["status"] == "pending"

    # list includes index_status for owner
    r3 = await client.get("/api/notebooks", headers=h)
    assert r3.status_code == 200
    items = r3.json()["items"]
    mine = next(x for x in items if x["id"] == nb.id)
    assert mine["index_status"] in ("pending", "indexing", "ready", "failed", "skipped")
