"""Admin fetch settings (concurrency / timeout / chunks)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.fetch_settings.runtime import apply_chunk_opts, get_cached_settings
from app.models.user import User


async def _admin(db_session) -> tuple[User, str]:
    u = User(phone="13800000110", name="admin", role="admin", status="active")
    u.set_password("adminpw1234")
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    token, _ = create_access_token(u.id, role="admin")
    return u, token


@pytest.mark.asyncio
async def test_fetch_settings_get_put(client: AsyncClient, db_session):
    _u, token = await _admin(db_session)
    h = {"Authorization": f"Bearer {token}"}

    r = await client.get("/api/admin/fetch-settings", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["max_concurrent"] == 2
    assert body["chunk_count"] == 4

    r2 = await client.put(
        "/api/admin/fetch-settings",
        headers=h,
        json={
            "max_concurrent": 4,
            "task_timeout_minutes": 45,
            "chunk_parallel_enabled": True,
            "chunk_count": 6,
            "chunk_min_mb": 30,
        },
    )
    assert r2.status_code == 200, r2.text
    got = r2.json()
    assert got["max_concurrent"] == 4
    assert got["task_timeout_minutes"] == 45
    assert got["chunk_count"] == 6
    assert got["chunk_min_mb"] == 30
    snap = get_cached_settings()
    assert snap.max_concurrent == 4
    assert snap.chunk_count == 6


@pytest.mark.asyncio
async def test_fetch_settings_validation(client: AsyncClient, db_session):
    _u, token = await _admin(db_session)
    h = {"Authorization": f"Bearer {token}"}
    r = await client.put(
        "/api/admin/fetch-settings",
        headers=h,
        json={
            "max_concurrent": 99,
            "task_timeout_minutes": 30,
            "chunk_parallel_enabled": True,
            "chunk_count": 4,
            "chunk_min_mb": 20,
        },
    )
    assert r.status_code == 422


def test_apply_chunk_opts_respects_min_size():
    from app.fetch_settings.runtime import set_runtime_snapshot

    set_runtime_snapshot(
        max_concurrent=2,
        task_timeout_minutes=30,
        chunk_parallel_enabled=True,
        chunk_count=4,
        chunk_min_mb=20,
    )
    small = apply_chunk_opts({}, filesize=5 * 1024 * 1024)
    assert small["concurrent_fragment_downloads"] == 1
    big = apply_chunk_opts({}, filesize=50 * 1024 * 1024)
    assert big["concurrent_fragment_downloads"] == 4

    set_runtime_snapshot(
        max_concurrent=2,
        task_timeout_minutes=30,
        chunk_parallel_enabled=False,
        chunk_count=8,
        chunk_min_mb=20,
    )
    off = apply_chunk_opts({}, filesize=50 * 1024 * 1024)
    assert off["concurrent_fragment_downloads"] == 1
