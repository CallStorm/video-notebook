"""字幕解析，以及内嵌 / 转写两条流水线。"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.llm.config_service import SttResolved
from app.models.notebook import Video
from app.models.user import User
from app.subtitles.srt import Cue, format_srt, parse_srt


def test_parse_srt_round_trip():
    raw = (
        "1\n"
        "00:00:01,200 --> 00:00:03,500\n"
        "你好\n"
        "\n"
        "2\n"
        "00:01:00.000 --> 00:01:02.250\n"
        "第二行\n"
        "接着说\n"
    )
    cues = parse_srt(raw)
    assert cues == [
        Cue(start_ms=1200, end_ms=3500, text="你好"),
        Cue(start_ms=60_000, end_ms=62_250, text="第二行\n接着说"),
    ]
    again = parse_srt(format_srt(cues))
    assert again == cues


def test_parse_srt_skips_empty_blocks():
    assert parse_srt("") == []
    assert parse_srt("not a subtitle") == []


def test_plain_transcript_is_not_timestamped():
    from app.subtitles.transcribe import parse_transcript_body

    parsed = parse_transcript_body(
        b'{"text":"\xe4\xbd\xa0\xe5\xa5\xbd\xe3\x80\x82\xe4\xb8\x96\xe7\x95\x8c\xe3\x80\x82","language":"Chinese"}',
        "verbose_json",
    )
    assert parsed.timestamped is False
    assert parsed.language == "Chinese"
    assert "你好" in parsed.text


def test_segments_are_timestamped():
    from app.subtitles.transcribe import parse_transcript_body

    body = (
        b'{"language":"chinese","segments":['
        b'{"start":0.0,"end":1.5,"text":"\xe4\xbd\xa0\xe5\xa5\xbd"},'
        b'{"start":1.5,"end":3.0,"text":"\xe4\xb8\x96\xe7\x95\x8c"}]}'
    )
    parsed = parse_transcript_body(body, "verbose_json")
    assert parsed.timestamped is True
    assert [cue.text for cue in parsed.cues] == ["你好", "世界"]
    assert parsed.cues[1].start_ms == 1500


def test_long_text_is_split_across_the_slice():
    from app.subtitles.cues import distribute, split_subtitle_lines

    text = "各位朋友，最近这一两年来啊。如果你要生活在中国大陆地区，恐怕有一种感觉。就是好像我们的政府没钱了。"
    lines = split_subtitle_lines(text)
    assert len(lines) >= 3
    cues = distribute(lines, 10_000, 16_000)
    assert cues[0].start_ms == 10_000
    assert cues[-1].end_ms == 16_000
    assert all(cue.end_ms > cue.start_ms for cue in cues)
    assert "。".join(cue.text.rstrip("。") for cue in cues if cue.text.endswith("。"))


def test_speech_ranges_prefer_silence_but_cap_length():
    from app.subtitles.media import speech_ranges

    # 40s，中间 10s 和 20s 附近有停顿，最长 18s
    ranges = speech_ranges(
        40_000,
        [(9_500, 10_500), (19_500, 20_500)],
        max_ms=18_000,
    )
    assert ranges[0] == (0, 10_000)
    assert ranges[-1][1] == 40_000
    assert all(end - start <= 18_000 for start, end in ranges)

    hard = speech_ranges(40_000, [], max_ms=18_000)
    assert hard == [(0, 18_000), (18_000, 36_000), (36_000, 40_000)]


@pytest.mark.asyncio
async def _owner(db_session, phone: str) -> User:
    user = User(phone=phone, name="字幕", role="user", status="active")
    user.set_password("userpw1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def _video(db_session, owner: User) -> Video:
    video = Video(
        owner_id=owner.id,
        source_type="upload",
        storage_key="a" * 40 + ".mp4",
        status="ready",
        title="clip.mp4",
        subtitle_status="pending",
    )
    db_session.add(video)
    await db_session.commit()
    await db_session.refresh(video)
    return video


@pytest.mark.asyncio
async def test_pipeline_saves_embedded_cues(db_session, monkeypatch):
    from app.subtitles.pipeline import run_subtitle_pipeline
    from app.subtitles.store import load_subtitle

    owner = await _owner(db_session, "13800000881")
    video = await _video(db_session, owner)

    def fake_extract(_path):
        return [Cue(0, 1500, "内嵌你好")], "zh"

    monkeypatch.setattr("app.subtitles.pipeline.extract_embedded_cues", fake_extract)
    await run_subtitle_pipeline(video.id, session=db_session)
    await db_session.refresh(video)
    subtitle, lines = await load_subtitle(db_session, video)
    assert video.subtitle_status == "ready"
    assert subtitle is not None
    assert subtitle.source == "embedded"
    assert [line.text for line in lines] == ["内嵌你好"]


@pytest.mark.asyncio
async def test_pipeline_falls_back_to_asr(db_session, monkeypatch):
    from app.subtitles.pipeline import run_subtitle_pipeline
    from app.subtitles.store import load_subtitle

    owner = await _owner(db_session, "13800000882")
    video = await _video(db_session, owner)

    monkeypatch.setattr("app.subtitles.pipeline.extract_embedded_cues", lambda _path: None)
    monkeypatch.setattr("app.subtitles.pipeline.prepare_audio", lambda path: path)

    async def fake_stt(_session):
        return SttResolved(
            provider="whisper",
            api_key="sk-test",
            model_name="whisper-1",
            config=None,
            base_url="https://example.com/v1",
        )

    async def fake_transcribe(_stt, _path):
        return [Cue(0, 2000, "转写结果")], "chinese"

    monkeypatch.setattr("app.subtitles.pipeline.get_active_stt", fake_stt)
    monkeypatch.setattr("app.subtitles.pipeline.transcribe_file", fake_transcribe)

    await run_subtitle_pipeline(video.id, session=db_session)
    await db_session.refresh(video)
    subtitle, lines = await load_subtitle(db_session, video)
    assert video.subtitle_status == "ready"
    assert subtitle is not None
    assert subtitle.source == "asr"
    assert lines[0].text == "转写结果"
    assert lines[0].end_ms == 2000


@pytest.mark.asyncio
async def test_regenerate_failure_keeps_previous_lines(db_session, monkeypatch):
    from app.subtitles.pipeline import run_subtitle_pipeline
    from app.subtitles.store import load_subtitle

    owner = await _owner(db_session, "13800000883")
    video = await _video(db_session, owner)

    def embedded(_path):
        return [Cue(0, 1000, "旧字幕")], "zh"

    monkeypatch.setattr("app.subtitles.pipeline.extract_embedded_cues", embedded)
    await run_subtitle_pipeline(video.id, session=db_session)

    def boom(_path):
        raise RuntimeError("ffmpeg 坏了")

    monkeypatch.setattr("app.subtitles.pipeline.extract_embedded_cues", boom)
    await run_subtitle_pipeline(video.id, session=db_session)
    await db_session.refresh(video)
    _subtitle, lines = await load_subtitle(db_session, video)
    assert video.subtitle_status == "failed"
    assert "ffmpeg 坏了" in (video.subtitle_error or "")
    assert [line.text for line in lines] == ["旧字幕"]


@pytest.mark.asyncio
async def test_rename_source(client: AsyncClient, db_session):
    user = User(phone="13800000998", name="改名", role="user", status="active")
    user.set_password("userpw1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token, _ = create_access_token(user.id, role="user")
    headers = {"Authorization": f"Bearer {token}"}
    notebook_id = (
        await client.post("/api/notebooks", headers=headers, json={"title": "n"})
    ).json()["id"]
    uploaded = await client.post(
        f"/api/notebooks/{notebook_id}/sources/upload",
        headers=headers,
        files={"file": ("hello.mp4", b"fake-video-bytes", "video/mp4")},
    )
    video_id = uploaded.json()["id"]
    renamed = await client.patch(
        f"/api/sources/{video_id}",
        headers=headers,
        json={"title": "新名字"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["title"] == "新名字"
    assert renamed.json()["overview_status"] == "pending"


@pytest.mark.asyncio
async def test_subtitle_endpoint_after_upload(client: AsyncClient, db_session):
    user = User(phone="13800000999", name="上传", role="user", status="active")
    user.set_password("userpw1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token, _ = create_access_token(user.id, role="user")
    headers = {"Authorization": f"Bearer {token}"}
    notebook_id = (
        await client.post("/api/notebooks", headers=headers, json={"title": "n"})
    ).json()["id"]
    uploaded = await client.post(
        f"/api/notebooks/{notebook_id}/sources/upload",
        headers=headers,
        files={"file": ("hello.mp4", b"fake-video-bytes", "video/mp4")},
    )
    assert uploaded.status_code == 201, uploaded.text
    video_id = uploaded.json()["id"]
    assert uploaded.json()["subtitle_status"] == "pending"

    got = await client.get(f"/api/sources/{video_id}/subtitle", headers=headers)
    assert got.status_code == 200, got.text
    assert got.json()["lines"] == []
    assert got.json()["subtitle_status"] == "pending"

    fetched = await client.post(
        f"/api/notebooks/{notebook_id}/sources/fetch",
        headers=headers,
        json={"url": "https://example.com/v.mp4"},
    )
    url_id = fetched.json()["id"]
    denied = await client.post(
        f"/api/sources/{url_id}/subtitle/regenerate", headers=headers
    )
    assert denied.status_code == 400
