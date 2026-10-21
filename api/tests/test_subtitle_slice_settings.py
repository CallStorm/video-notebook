"""Admin subtitle slice settings (ASR silence chunking)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.user import User
from app.subtitle_slice_settings.runtime import get_cached_settings


async def _admin(db_session) -> tuple[User, str]:
    u = User(phone="13800000111", name="admin", role="admin", status="active")
    u.set_password("adminpw1234")
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    token, _ = create_access_token(u.id, role="admin")
    return u, token


@pytest.mark.asyncio
async def test_subtitle_slice_settings_get_put(client: AsyncClient, db_session):
    _u, token = await _admin(db_session)
    h = {"Authorization": f"Bearer {token}"}

    r = await client.get("/api/admin/subtitle-slice-settings", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["max_slice_seconds"] == 30
    assert body["min_slice_ms"] == 600
    assert body["silence_noise_db"] == -32.0
    assert body["silence_min_duration_s"] == 0.3
    assert body["min_silence_for_cut_ms"] == 200

    r2 = await client.put(
        "/api/admin/subtitle-slice-settings",
        headers=h,
        json={
            "max_slice_seconds": 45,
            "min_slice_ms": 800,
            "silence_noise_db": -35,
            "silence_min_duration_s": 0.2,
            "min_silence_for_cut_ms": 150,
        },
    )
    assert r2.status_code == 200, r2.text
    got = r2.json()
    assert got["max_slice_seconds"] == 45
    assert got["min_slice_ms"] == 800
    assert got["silence_noise_db"] == -35.0
    assert got["silence_min_duration_s"] == 0.2
    assert got["min_silence_for_cut_ms"] == 150
    snap = get_cached_settings()
    assert snap.max_slice_seconds == 45
    assert snap.max_slice_ms == 45_000
    assert snap.min_silence_for_cut_ms == 150


@pytest.mark.asyncio
async def test_subtitle_slice_settings_validation(client: AsyncClient, db_session):
    _u, token = await _admin(db_session)
    h = {"Authorization": f"Bearer {token}"}
    r = await client.put(
        "/api/admin/subtitle-slice-settings",
        headers=h,
        json={
            "max_slice_seconds": 99,
            "min_slice_ms": 600,
            "silence_noise_db": -32,
            "silence_min_duration_s": 0.3,
            "min_silence_for_cut_ms": 200,
        },
    )
    assert r.status_code == 422


def test_speech_ranges_respects_min_silence_for_cut():
    from app.subtitles.media import speech_ranges

    silences = [(9_900, 10_050)]  # 150ms silence
    # too short for default 200ms cut threshold -> hard cut by max
    ignored = speech_ranges(40_000, silences, max_ms=18_000, min_silence_for_cut_ms=200)
    assert ignored == [(0, 18_000), (18_000, 36_000), (36_000, 40_000)]

    used = speech_ranges(40_000, silences, max_ms=18_000, min_silence_for_cut_ms=100)
    assert used[0] == (0, 9_975)
