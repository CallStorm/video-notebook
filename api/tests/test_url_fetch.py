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
