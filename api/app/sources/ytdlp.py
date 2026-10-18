"""yt-dlp / direct-URL download helpers for URL sources."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_DIRECT_SUFFIXES = {".mp4", ".webm", ".mkv", ".mov", ".m4v"}


class FetchDownloadError(RuntimeError):
    """Failed to download a playable file."""


@dataclass(frozen=True)
class DownloadResult:
    video_path: Path
    title: str | None
    subtitle_path: Path | None
    subtitle_language: str | None


def download_url(url: str, work_dir: Path) -> DownloadResult:
    """Download a video (and optional platform subtitles) into work_dir."""
    work_dir.mkdir(parents=True, exist_ok=True)
    if _looks_like_direct_media(url):
        return _download_direct(url, work_dir)
    return _download_with_ytdlp(url, work_dir)


def _looks_like_direct_media(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(path.endswith(suf) for suf in _DIRECT_SUFFIXES)


def _download_direct(url: str, work_dir: Path) -> DownloadResult:
    import httpx

    suffix = Path(urlparse(url).path).suffix.lower() or ".mp4"
    dest = work_dir / f"direct{suffix}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
    }
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=120.0, headers=headers) as resp:
            if resp.status_code >= 400:
                raise FetchDownloadError(f"HTTP {resp.status_code} 下载失败")
            ctype = (resp.headers.get("content-type") or "").lower()
            if ctype and not any(x in ctype for x in ("video", "octet-stream", "mp4", "webm")):
                # still allow if URL looked like media
                logger.warning("unexpected content-type for direct media: %s", ctype)
            with dest.open("wb") as out:
                for chunk in resp.iter_bytes():
                    out.write(chunk)
    except FetchDownloadError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise FetchDownloadError(_clean_error(exc)) from exc

    if not dest.exists() or dest.stat().st_size <= 0:
        raise FetchDownloadError("直接下载结果为空")
    name = Path(urlparse(url).path).stem or "video"
    return DownloadResult(
        video_path=dest,
        title=name[:255],
        subtitle_path=None,
        subtitle_language=None,
    )


def _download_with_ytdlp(url: str, work_dir: Path) -> DownloadResult:
    import yt_dlp

    from app.core.config import get_settings

    settings = get_settings()
    outtmpl = str(work_dir / "%(id)s.%(ext)s")
    opts: dict = {
        "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
        "merge_output_format": "mp4",
        "outtmpl": outtmpl,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en", "zh-Hans", "zh-Hant", "zh", "en-US"],
        "subtitlesformat": "srt/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "socket_timeout": 30,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            )
        },
    }
    cookies_file = getattr(settings, "ytdlp_cookies_file", None)
    cookies_browser = getattr(settings, "ytdlp_cookies_from_browser", None)
    if cookies_file:
        path = Path(cookies_file)
        if path.is_file():
            opts["cookiefile"] = str(path)
    elif cookies_browser:
        # e.g. "chrome" or "chrome:Default"
        parts = str(cookies_browser).split(":", 1)
        opts["cookiesfrombrowser"] = tuple(parts)

    info: dict | None = None
    try:
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

        def _run():
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=True)

        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(_run)
            try:
                info = fut.result(timeout=180)
            except FuturesTimeout as exc:
                raise FetchDownloadError(
                    "抓取超时（可能卡在浏览器 Cookie/钥匙串授权）。"
                    "请在本机允许钥匙串访问，或改用 YTDLP_COOKIES_FILE。"
                ) from exc
    except FetchDownloadError:
        raise
    except Exception as exc:  # noqa: BLE001
        msg = _clean_error(exc)
        if "Sign in to confirm" in msg or "not a bot" in msg:
            msg += (
                " 请在 .env 设置 YTDLP_COOKIES_FROM_BROWSER=chrome "
                "或 YTDLP_COOKIES_FILE=/path/to/cookies.txt 后重试。"
            )
        raise FetchDownloadError(msg) from exc

    if not info:
        raise FetchDownloadError("yt-dlp 没有返回视频信息")

    video_path = _find_video_file(work_dir, info)
    if video_path is None:
        raise FetchDownloadError("yt-dlp 下载完成但找不到视频文件")

    sub_path, sub_lang = _find_subtitle_file(work_dir, info)
    title = info.get("title")
    if isinstance(title, str):
        title = title.strip() or None
    else:
        title = None

    return DownloadResult(
        video_path=video_path,
        title=title,
        subtitle_path=sub_path,
        subtitle_language=sub_lang,
    )


def _clean_error(exc: BaseException) -> str:
    text = str(exc) or exc.__class__.__name__
    return _ANSI_RE.sub("", text).strip()


def _find_video_file(work_dir: Path, info: dict) -> Path | None:
    requested = info.get("requested_downloads") or []
    for item in requested:
        filepath = item.get("filepath") if isinstance(item, dict) else None
        if filepath:
            path = Path(filepath)
            if path.exists() and path.suffix.lower() in {".mp4", ".webm", ".mkv", ".mov"}:
                return path

    vid = str(info.get("id") or "")
    preferred = (".mp4", ".webm", ".mkv", ".mov")
    candidates = [
        p
        for p in work_dir.iterdir()
        if p.is_file() and p.suffix.lower() in preferred and not p.name.endswith(".part")
    ]
    candidates.sort(
        key=lambda p: (1 if p.suffix.lower() == ".mp4" else 0, p.stat().st_size),
        reverse=True,
    )
    if vid:
        for path in candidates:
            if path.stem == vid or path.stem.startswith(vid):
                return path
    return candidates[0] if candidates else None


def _find_subtitle_file(work_dir: Path, info: dict) -> tuple[Path | None, str | None]:
    vid = str(info.get("id") or "")
    srt_files = sorted(work_dir.glob("*.srt"))
    if not srt_files:
        return None, None

    preferred_langs = ("en", "en-US", "zh-Hans", "zh-Hant", "zh")
    scored: list[tuple[int, Path, str | None]] = []
    for path in srt_files:
        name = path.name
        lang: str | None = None
        if vid and name.startswith(vid + "."):
            rest = name[len(vid) + 1 : -4]
            lang = rest or None
        score = 100
        if lang:
            try:
                score = preferred_langs.index(lang)
            except ValueError:
                score = 50
        scored.append((score, path, lang))
    scored.sort(key=lambda row: row[0])
    best = scored[0]
    return best[1], best[2]
