"""Search-result preview: resolve playable URL via yt-dlp, proxy (or ffmpeg-merge) stream."""
from __future__ import annotations

import logging
import secrets
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Any, Iterator

import httpx

from app.core.errors import BadRequestError, NotFoundError
from app.fetch_network.runtime import apply_ytdlp_opts
from app.media.ffmpeg_path import ensure_ffmpeg_on_path, resolve_ffmpeg_dir

logger = logging.getLogger(__name__)

_TTL_SECONDS = 600
_STORE: dict[str, "PreviewEntry"] = {}
_LOCK = threading.Lock()

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


@dataclass
class PreviewEntry:
    video_url: str
    audio_url: str | None
    headers: dict[str, str]
    title: str | None
    expires_at: float

    @property
    def needs_merge(self) -> bool:
        return bool(self.audio_url)


def _purge_expired() -> None:
    now = time.time()
    dead = [k for k, v in _STORE.items() if v.expires_at <= now]
    for k in dead:
        _STORE.pop(k, None)


def resolve_preview(url: str) -> tuple[str, PreviewEntry]:
    """Extract stream URLs for *url*; return (token, entry)."""
    cleaned = (url or "").strip()
    if not cleaned.startswith(("http://", "https://")):
        raise BadRequestError("无效的视频链接")

    video_url, audio_url, headers, title = _extract_streams(cleaned)
    entry = PreviewEntry(
        video_url=video_url,
        audio_url=audio_url,
        headers=headers,
        title=title,
        expires_at=time.time() + _TTL_SECONDS,
    )
    token = secrets.token_urlsafe(24)
    with _LOCK:
        _purge_expired()
        _STORE[token] = entry
    logger.info(
        "preview resolved token=%s merge=%s title=%s",
        token[:8],
        entry.needs_merge,
        (title or "")[:40],
    )
    return token, entry


def get_preview(token: str) -> PreviewEntry:
    with _LOCK:
        _purge_expired()
        entry = _STORE.get(token)
    if entry is None:
        raise NotFoundError("预览已过期，请重新打开")
    return entry


def _js_runtimes() -> dict:
    import shutil
    from pathlib import Path

    deno = shutil.which("deno") or str(Path.home() / ".deno" / "bin" / "deno")
    if Path(deno).is_file():
        return {"deno": {"path": deno}}
    node = shutil.which("node")
    if node:
        return {"node": {"path": node}}
    return {"deno": {}}


def _extract_streams(url: str) -> tuple[str, str | None, dict[str, str], str | None]:
    import yt_dlp

    from app.media.ffmpeg_path import ytdlp_ffmpeg_location

    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": 30,
        # Prefer combined A+V; else best video+audio (DASH) for ffmpeg merge.
        "format": (
            "best[acodec!=none][vcodec!=none][protocol^=http][protocol!=m3u8_native]/"
            "best[acodec!=none][vcodec!=none]/"
            "bv*+ba/b"
        ),
        "js_runtimes": _js_runtimes(),
    }
    ffmpeg_loc = ytdlp_ffmpeg_location()
    if ffmpeg_loc:
        opts["ffmpeg_location"] = ffmpeg_loc
    opts = apply_ytdlp_opts(opts, url=url)

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:  # noqa: BLE001
        raise BadRequestError(f"无法解析预览：{_clean(exc)}") from exc

    if not info:
        raise BadRequestError("无法解析预览：无视频信息")

    title = (info.get("title") or None)
    headers = _headers_from_info(info, url)

    requested = info.get("requested_formats")
    if isinstance(requested, list) and len(requested) >= 2:
        video_f = next(
            (f for f in requested if f.get("vcodec") not in (None, "none")),
            None,
        )
        audio_f = next(
            (
                f
                for f in requested
                if f.get("acodec") not in (None, "none")
                and f.get("vcodec") in (None, "none")
            ),
            None,
        )
        if video_f and audio_f and video_f.get("url") and audio_f.get("url"):
            v_headers = _headers_from_format(video_f, fallback=headers)
            a_headers = _headers_from_format(audio_f, fallback=v_headers)
            merged = {**a_headers, **v_headers}
            return str(video_f["url"]), str(audio_f["url"]), merged, title

    direct = info.get("url")
    acodec = info.get("acodec")
    vcodec = info.get("vcodec")
    if direct and vcodec not in (None, "none") and acodec not in (None, "none"):
        return str(direct), None, headers, title

    for fmt in reversed(info.get("formats") or []):
        if not isinstance(fmt, dict):
            continue
        if fmt.get("vcodec") in (None, "none") or fmt.get("acodec") in (None, "none"):
            continue
        if not fmt.get("url"):
            continue
        proto = fmt.get("protocol") or ""
        if "m3u8" in proto:
            continue
        return (
            str(fmt["url"]),
            None,
            _headers_from_format(fmt, fallback=headers),
            title,
        )

    if direct and vcodec not in (None, "none"):
        logger.warning("preview video-only for %s", url[:80])
        return str(direct), None, headers, title

    raise BadRequestError("该视频没有可预览的直链格式")


def _headers_from_info(info: dict[str, Any], page_url: str) -> dict[str, str]:
    http_headers = (
        info.get("http_headers") if isinstance(info.get("http_headers"), dict) else {}
    )
    headers = {str(k): str(v) for k, v in http_headers.items()}
    headers.setdefault("User-Agent", _UA)
    if "bilibili.com" in page_url:
        headers["Referer"] = "https://www.bilibili.com/"
    else:
        headers.setdefault("Referer", page_url)
    return headers


def _headers_from_format(
    fmt: dict[str, Any], *, fallback: dict[str, str]
) -> dict[str, str]:
    http_headers = (
        fmt.get("http_headers") if isinstance(fmt.get("http_headers"), dict) else {}
    )
    out = dict(fallback)
    out.update({str(k): str(v) for k, v in http_headers.items()})
    return out


def _clean(exc: BaseException) -> str:
    msg = str(exc).strip() or exc.__class__.__name__
    return msg[:240]


def iter_preview_bytes(entry: PreviewEntry) -> Iterator[bytes]:
    """Yield media bytes: ffmpeg remux for DASH, else HTTP proxy."""
    if entry.needs_merge:
        yield from _iter_ffmpeg_merge(entry)
        return
    yield from _iter_http_proxy(entry.video_url, entry.headers)


def _iter_http_proxy(url: str, headers: dict[str, str]) -> Iterator[bytes]:
    with httpx.stream(
        "GET",
        url,
        headers=headers,
        follow_redirects=True,
        timeout=httpx.Timeout(30.0, read=120.0),
    ) as resp:
        if resp.status_code >= 400:
            raise BadRequestError(f"上游视频拉取失败 HTTP {resp.status_code}")
        for chunk in resp.iter_bytes(65536):
            if chunk:
                yield chunk


def _ffmpeg_bin() -> str:
    import os
    from pathlib import Path

    ensure_ffmpeg_on_path()
    directory = resolve_ffmpeg_dir()
    if directory is None:
        raise BadRequestError("未找到 ffmpeg，无法合并音视频预览")
    name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    path = Path(directory) / name
    if not path.is_file():
        raise BadRequestError("未找到 ffmpeg，无法合并音视频预览")
    return str(path)


def _header_block(headers: dict[str, str]) -> str:
    lines = [f"{k}: {v}" for k, v in headers.items() if k.lower() != "user-agent"]
    return "\r\n".join(lines) + "\r\n"


def _iter_ffmpeg_merge(entry: PreviewEntry) -> Iterator[bytes]:
    assert entry.audio_url
    ffmpeg = _ffmpeg_bin()
    ua = entry.headers.get("User-Agent") or _UA
    hdr = _header_block(entry.headers)
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-user_agent",
        ua,
        "-headers",
        hdr,
        "-i",
        entry.video_url,
        "-user_agent",
        ua,
        "-headers",
        hdr,
        "-i",
        entry.audio_url,
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c",
        "copy",
        "-f",
        "mp4",
        "-movflags",
        "frag_keyframe+empty_moov+default_base_moof",
        "pipe:1",
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
    )
    assert proc.stdout is not None
    try:
        while True:
            chunk = proc.stdout.read(65536)
            if not chunk:
                break
            yield chunk
        rc = proc.wait(timeout=30)
        if rc != 0:
            err = (proc.stderr.read() if proc.stderr else b"").decode("utf-8", "ignore")[
                -400:
            ]
            logger.warning("ffmpeg preview merge failed rc=%s err=%s", rc, err)
            raise BadRequestError("音视频合并预览失败")
    finally:
        if proc.poll() is None:
            proc.kill()
        if proc.stdout:
            proc.stdout.close()
        if proc.stderr:
            proc.stderr.close()
