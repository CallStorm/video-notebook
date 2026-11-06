"""抖音域名规则、DTK 解析和后台配置。"""
from __future__ import annotations

import time
from pathlib import Path

import httpx
import pytest
from httpx import AsyncClient

from app.fetch_network.douyin import (
    DouyinParserConfig,
    match_host_rule,
    normalize_host_rule,
    normalize_host_rules,
)
from app.sources.douyin_dtk import FetchDownloadError, _parse, _pick_play_url
from app.sources.ytdlp import DownloadResult, download_url


def test_default_rules_match_share_hosts() -> None:
    rules = ["v.douyin.com", "douyin.com", "iesdouyin.com"]
    assert match_host_rule("https://v.douyin.com/tIqoVziKWl8/", rules) == "v.douyin.com"
    assert match_host_rule("https://www.douyin.com/video/123", rules) == "douyin.com"
    assert match_host_rule("https://www.iesdouyin.com/share/video/1", rules) == "iesdouyin.com"
    assert match_host_rule("https://www.youtube.com/watch?v=abc", rules) is None


def test_normalize_host_rule_accepts_pasted_url() -> None:
    assert normalize_host_rule("HTTPS://www.Douyin.com/video/1") == "www.douyin.com"
    assert normalize_host_rules(["douyin.com", "https://douyin.com/x", "v.douyin.com"]) == [
        "douyin.com",
        "v.douyin.com",
    ]


def test_parse_uses_wait_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/parse"
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "kind": "video",
                    "title": "作品",
                    "media": {
                        "video": {"url": "https://cdn.example/a.mp4", "watermark": False},
                        "streams": [],
                    },
                },
                "error": None,
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    content = _parse(
        client,
        "http://parser",
        "https://v.douyin.com/abc/",
        time.monotonic() + 30,
        {},
    )
    assert _pick_play_url(content) == "https://cdn.example/a.mp4"


def test_parse_polls_after_accept_and_rejects_album() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if request.url.path == "/api/v1/parse":
            return httpx.Response(
                202,
                json={"success": True, "data": {"task_id": "t1", "state": "queued"}, "error": None},
            )
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": {"state": "done", "data": {"kind": "image_album", "title": "图"}},
                "error": None,
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(FetchDownloadError, match="图文或直播"):
        _parse(client, "http://parser", "https://v.douyin.com/abc/", time.monotonic() + 30, {})
    assert calls["n"] == 2


def test_pick_play_url_prefers_higher_mp4_stream() -> None:
    content = {
        "kind": "video",
        "media": {
            "video": {},
            "streams": [
                {"url": "https://cdn.example/low.mp4", "watermark": False, "format": "mp4", "height": 720},
                {"url": "https://cdn.example/high.mp4", "watermark": False, "format": "mp4", "height": 1080},
                {"url": "https://cdn.example/wm.mp4", "watermark": True, "format": "mp4", "height": 1440},
            ],
        },
    }
    assert _pick_play_url(content) == "https://cdn.example/high.mp4"


def test_download_url_routes_douyin_and_leaves_youtube(tmp_path: Path, monkeypatch) -> None:
    from app.fetch_settings.runtime import FetchSettingsSnapshot

    monkeypatch.setattr(
        "app.fetch_network.douyin.read_douyin_parser",
        lambda: DouyinParserConfig(
            base_url="http://127.0.0.1:8001",
            api_key="secret",
            host_rules=("v.douyin.com", "douyin.com", "iesdouyin.com"),
        ),
    )
    monkeypatch.setattr(
        "app.fetch_settings.runtime.get_settings_fresh",
        lambda: FetchSettingsSnapshot(),
    )
    seen: dict[str, str] = {}

    def fake_douyin(url: str, work_dir: Path, **kwargs):
        seen["url"] = url
        dest = work_dir / "v.mp4"
        dest.write_bytes(b"1234")
        return DownloadResult(video_path=dest, title="抖音", subtitle_path=None, subtitle_language=None)

    def fake_ytdlp(url: str, work_dir: Path):
        seen["ytdlp"] = url
        dest = work_dir / "y.mp4"
        dest.write_bytes(b"1234")
        return DownloadResult(video_path=dest, title="YT", subtitle_path=None, subtitle_language=None)

    monkeypatch.setattr("app.sources.douyin_dtk.download_douyin", fake_douyin)
    monkeypatch.setattr("app.sources.ytdlp._download_with_ytdlp", fake_ytdlp)

    got = download_url("https://v.douyin.com/abc/", tmp_path / "dy")
    assert got.title == "抖音"
    assert seen["url"] == "https://v.douyin.com/abc/"

    got_yt = download_url("https://www.youtube.com/watch?v=abc", tmp_path / "yt")
    assert got_yt.title == "YT"
    assert seen["ytdlp"].startswith("https://www.youtube.com/")


def test_download_url_requires_parser_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.fetch_network.douyin.read_douyin_parser",
        lambda: DouyinParserConfig(
            base_url="http://127.0.0.1:8001",
            api_key=None,
            host_rules=("douyin.com",),
        ),
    )
    with pytest.raises(FetchDownloadError, match="未配置抖音解析服务"):
        download_url("https://www.douyin.com/video/1", tmp_path)


@pytest.mark.asyncio
async def test_admin_saves_douyin_parser_without_returning_key(
    client: AsyncClient, db_session
) -> None:
    from app.core.security import create_access_token
    from app.models.user import User

    admin = User(phone="13800008881", name="admin", role="admin", status="active")
    admin.set_password("adminpw1234")
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    token, _ = create_access_token(admin.id, role="admin")
    headers = {"Authorization": f"Bearer {token}"}

    saved = await client.put(
        "/api/admin/fetch-network/douyin-parser",
        headers=headers,
        json={
            "base_url": "http://127.0.0.1:8001",
            "api_key": "dtk-secret-key",
            "host_rules": ["https://www.douyin.com/video/1", "iesdouyin.com"],
        },
    )
    assert saved.status_code == 200, saved.text
    parser = saved.json()["douyin_parser"]
    assert parser["api_key_set"] is True
    assert parser["host_rules"] == ["www.douyin.com", "iesdouyin.com"]
    assert "dtk-secret-key" not in saved.text

    kept = await client.put(
        "/api/admin/fetch-network/douyin-parser",
        headers=headers,
        json={"base_url": "http://127.0.0.1:8001/", "api_key": None, "host_rules": ["douyin.com"]},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["douyin_parser"]["api_key_set"] is True
    assert kept.json()["douyin_parser"]["base_url"] == "http://127.0.0.1:8001"
