"""URL source fetch pipeline (yt-dlp)."""
from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.notebook import Video
from app.models.user import User

pytestmark = pytest.mark.asyncio


async def _user(db_session, phone="13800000999", role="user") -> tuple[User, str]:
    u = User(phone=phone, name=phone, role=role, status="active")
    u.set_password("userpw1234")
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    token, _ = create_access_token(u.id, role=role)
    return u, token


async def test_fetch_url_stays_pending_in_test_env(client: AsyncClient, db_session):
    _u, token = await _user(db_session)
    h = {"Authorization": f"Bearer {token}"}
    nb_id = (await client.post("/api/notebooks", headers=h, json={"title": "n"})).json()["id"]
    r = await client.post(
        f"/api/notebooks/{nb_id}/sources/fetch",
        headers=h,
        json={"url": "https://www.youtube.com/watch?v=ZIVMXMahZM4"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["source_type"] == "url"
    assert body["status"] == "pending"
    assert body["storage_key"] is None


async def test_run_fetch_pipeline_ready(client: AsyncClient, db_session, tmp_path, monkeypatch):
    from app.sources import fetch as fetch_mod
    from app.sources.ytdlp import DownloadResult

    _u, token = await _user(db_session, phone="13800000998")
    h = {"Authorization": f"Bearer {token}"}
    nb_id = (await client.post("/api/notebooks", headers=h, json={"title": "n"})).json()["id"]
    created = (
        await client.post(
            f"/api/notebooks/{nb_id}/sources/fetch",
            headers=h,
            json={"url": "https://example.com/clip.mp4"},
        )
    ).json()
    video_id = created["id"]

    video_file = tmp_path / "clip.mp4"
    video_file.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64)
    sub_file = tmp_path / "clip.en.srt"
    sub_file.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHello platform\n",
        encoding="utf-8",
    )

    def fake_download(url: str, work_dir: Path) -> DownloadResult:
        dest = work_dir / "clip.mp4"
        dest.write_bytes(video_file.read_bytes())
        srt = work_dir / "clip.en.srt"
        srt.write_text(sub_file.read_text(encoding="utf-8"), encoding="utf-8")
        return DownloadResult(
            video_path=dest,
            title="Mock Title",
            subtitle_path=srt,
            subtitle_language="en",
        )

    monkeypatch.setattr(fetch_mod, "download_url", fake_download)
    monkeypatch.setattr(
        "app.services.sources._ffprobe",
        lambda _key: {"duration_ms": 1000, "width": 320, "height": 240},
    )

    await fetch_mod.run_fetch_pipeline(video_id, session=db_session)

    video = (
        await db_session.execute(select(Video).where(Video.id == video_id))
    ).scalar_one()
    assert video.status == "ready"
    assert video.storage_key
    assert video.title == "Mock Title"
    assert video.duration_ms == 1000
    assert video.subtitle_status == "ready"

    play = await client.get(f"/api/sources/{video_id}/play_url", headers=h)
    assert play.status_code == 200
    assert "token=" in play.json()["url"]


async def test_run_fetch_pipeline_failed(client: AsyncClient, db_session, monkeypatch):
    from app.sources import fetch as fetch_mod
    from app.sources.ytdlp import FetchDownloadError

    _u, token = await _user(db_session, phone="13800000997")
    h = {"Authorization": f"Bearer {token}"}
    nb_id = (await client.post("/api/notebooks", headers=h, json={"title": "n"})).json()["id"]
    video_id = (
        await client.post(
            f"/api/notebooks/{nb_id}/sources/fetch",
            headers=h,
            json={"url": "https://example.com/bad.mp4"},
        )
    ).json()["id"]

    def boom(url: str, work_dir: Path):
        raise FetchDownloadError("unsupported url")

    monkeypatch.setattr(fetch_mod, "download_url", boom)
    await fetch_mod.run_fetch_pipeline(video_id, session=db_session)

    video = (
        await db_session.execute(select(Video).where(Video.id == video_id))
    ).scalar_one()
    assert video.status == "failed"
    assert video.error_message and "unsupported url" in video.error_message


async def test_retry_fetch_requeues_failed(client: AsyncClient, db_session, monkeypatch):
    from app.sources import fetch as fetch_mod
    from app.sources.ytdlp import FetchDownloadError

    _u, token = await _user(db_session, phone="13800000996")
    h = {"Authorization": f"Bearer {token}"}
    nb_id = (await client.post("/api/notebooks", headers=h, json={"title": "n"})).json()["id"]
    video_id = (
        await client.post(
            f"/api/notebooks/{nb_id}/sources/fetch",
            headers=h,
            json={"url": "https://example.com/bad.mp4"},
        )
    ).json()["id"]

    monkeypatch.setattr(
        fetch_mod,
        "download_url",
        lambda url, work_dir: (_ for _ in ()).throw(FetchDownloadError("boom")),
    )
    await fetch_mod.run_fetch_pipeline(video_id, session=db_session)
    video = (await db_session.execute(select(Video).where(Video.id == video_id))).scalar_one()
    assert video.status == "failed"

    r = await client.post(f"/api/sources/{video_id}/retry-fetch", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert body["error_message"] is None


async def test_media_sweep_marks_stale_probing(db_session, monkeypatch):
    from datetime import datetime, timedelta

    from sqlalchemy import text

    from app.db.session import get_sessionmaker
    from app.fetch_settings.runtime import FetchSettingsSnapshot, set_runtime_snapshot
    from app.media.worker import sweep_stale_media

    set_runtime_snapshot(
        max_concurrent=2,
        task_timeout_minutes=30,
        chunk_parallel_enabled=True,
        chunk_count=4,
        chunk_min_mb=20,
    )
    monkeypatch.setattr(
        "app.media.worker.get_settings_fresh",
        lambda: FetchSettingsSnapshot(task_timeout_minutes=30),
    )

    u, _token = await _user(db_session, phone="13800000995")
    video = Video(
        owner_id=u.id,
        source_type="url",
        source_url="https://example.com/stuck.mp4",
        title="stuck",
        status="probing",
        subtitle_status="pending",
        overview_status="pending",
    )
    db_session.add(video)
    await db_session.commit()
    await db_session.refresh(video)
    video_id = video.id
    stale = (datetime.utcnow() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    await db_session.execute(
        text("UPDATE videos SET updated_at = :ts WHERE id = :id"),
        {"ts": stale, "id": video_id},
    )
    await db_session.commit()

    count = await sweep_stale_media(datetime.utcnow())
    assert count == 1

    async with get_sessionmaker()() as session:
        got = await session.get(Video, video_id)
        assert got is not None
        assert got.status == "failed"
        assert "超时" in (got.error_message or "")


async def test_kick_fetch_enqueues_pipeline(monkeypatch):
    calls: list[tuple] = []

    def fake_enqueue(video_id, *, stage="full", force=False):
        calls.append((video_id, stage, force))

    monkeypatch.setattr("app.media.enqueue.enqueue_pipeline", fake_enqueue)
    from app.sources.fetch import kick_fetch_job

    kick_fetch_job(42)
    assert calls == [(42, "full", False)]
