"""Admin overview settings + auto overview after subtitle."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.notebook import SubtitleLine, Video
from app.models.user import User
from app.overview_settings.defaults import DEFAULT_OVERVIEW_PROMPT
from app.subtitles.srt import Cue


async def _admin(db_session) -> tuple[User, str]:
    u = User(phone="13800000131", name="admin-ov", role="admin", status="active")
    u.set_password("adminpw1234")
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    token, _ = create_access_token(u.id, role="admin")
    return u, token


@pytest.mark.asyncio
async def test_overview_settings_get_put_and_reset(client: AsyncClient, db_session):
    _u, token = await _admin(db_session)
    h = {"Authorization": f"Bearer {token}"}

    r = await client.get("/api/admin/overview-settings", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["auto_generate_after_subtitle"] is True
    assert body["is_custom_prompt"] is False
    assert body["prompt_text"] == DEFAULT_OVERVIEW_PROMPT
    assert body["default_prompt"] == DEFAULT_OVERVIEW_PROMPT

    r2 = await client.put(
        "/api/admin/overview-settings",
        headers=h,
        json={
            "auto_generate_after_subtitle": False,
            "prompt_text": "只写一句话概览。",
        },
    )
    assert r2.status_code == 200, r2.text
    b2 = r2.json()
    assert b2["auto_generate_after_subtitle"] is False
    assert b2["is_custom_prompt"] is True
    assert b2["prompt_text"] == "只写一句话概览。"

    r3 = await client.put(
        "/api/admin/overview-settings",
        headers=h,
        json={"auto_generate_after_subtitle": True, "prompt_text": "  "},
    )
    assert r3.status_code == 200, r3.text
    b3 = r3.json()
    assert b3["auto_generate_after_subtitle"] is True
    assert b3["is_custom_prompt"] is False
    assert b3["prompt_text"] == DEFAULT_OVERVIEW_PROMPT


@pytest.mark.asyncio
async def test_pipeline_auto_overview_when_enabled(db_session, monkeypatch):
    from app.models.overview_settings import OverviewSettingsConfig
    from app.subtitles.pipeline import run_subtitle_pipeline
    from app.subtitles.store import load_subtitle

    from app.services.overview_settings import get_overview_settings_row
    row = await get_overview_settings_row(db_session)
    row.auto_generate_after_subtitle = True
    row.prompt_text = None
    db_session.add(row)
    await db_session.commit()
    owner = User(phone="13800000891", name="ov", role="user", status="active")
    owner.set_password("userpw1234")
    db_session.add(owner)
    await db_session.commit()
    await db_session.refresh(owner)

    video = Video(
        owner_id=owner.id,
        source_type="upload",
        storage_key="b" * 40 + ".mp4",
        status="ready",
        title="测试片",
        subtitle_status="pending",
        overview_status="pending",
    )
    db_session.add(video)
    await db_session.commit()
    await db_session.refresh(video)

    monkeypatch.setattr(
        "app.subtitles.pipeline.extract_embedded_cues",
        lambda _path: ([Cue(0, 1500, "今天讲减脂")], "zh"),
    )

    async def fake_overview(session, lines, *, video=None):
        assert any("减脂" in (ln.text or "") for ln in lines)
        return "这是自动生成的概览。"

    monkeypatch.setattr("app.subtitles.pipeline.write_overview", fake_overview)

    await run_subtitle_pipeline(video.id, session=db_session)
    await db_session.refresh(video)
    assert video.subtitle_status == "ready"
    assert video.overview_status == "ready"
    assert video.overview_text == "这是自动生成的概览。"
    _sub, lines = await load_subtitle(db_session, video)
    assert [ln.text for ln in lines] == ["今天讲减脂"]


@pytest.mark.asyncio
async def test_pipeline_skips_overview_when_auto_off(db_session, monkeypatch):
    from app.models.overview_settings import OverviewSettingsConfig
    from app.subtitles.pipeline import run_subtitle_pipeline

    from app.services.overview_settings import get_overview_settings_row
    row = await get_overview_settings_row(db_session)
    row.auto_generate_after_subtitle = False
    row.prompt_text = None
    db_session.add(row)
    await db_session.commit()
    owner = User(phone="13800000892", name="ov2", role="user", status="active")
    owner.set_password("userpw1234")
    db_session.add(owner)
    await db_session.commit()
    await db_session.refresh(owner)

    video = Video(
        owner_id=owner.id,
        source_type="upload",
        storage_key="c" * 40 + ".mp4",
        status="ready",
        title="clip",
        subtitle_status="pending",
        overview_status="pending",
    )
    db_session.add(video)
    await db_session.commit()
    await db_session.refresh(video)

    monkeypatch.setattr(
        "app.subtitles.pipeline.extract_embedded_cues",
        lambda _path: ([Cue(0, 1000, "hello")], "zh"),
    )

    called = {"n": 0}

    async def boom(*_a, **_k):
        called["n"] += 1
        raise AssertionError("should not write overview")

    monkeypatch.setattr("app.subtitles.pipeline.write_overview", boom)

    await run_subtitle_pipeline(video.id, session=db_session)
    await db_session.refresh(video)
    assert video.subtitle_status == "ready"
    assert video.overview_status == "pending"
    assert called["n"] == 0
