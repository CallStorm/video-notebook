"""通过已部署的 Douyin_TikTok_Download_API 解析抖音链接并下载视频。"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import httpx

from app.sources.ytdlp import DownloadResult, FetchDownloadError

logger = logging.getLogger(__name__)

_WAIT_SECONDS = 25
_POLL_INTERVAL = 2.0
_UNAVAILABLE = frozenset(
    {
        "IDENTITY_POOL_EXHAUSTED",
        "IDENTITY_LOGIN_REQUIRED",
        "UPSTREAM_RISK_CONTROL",
        "ENDPOINT_CIRCUIT_OPEN",
        "SIGNING_FAILED",
    }
)


def download_douyin(
    url: str,
    work_dir: Path,
    *,
    base_url: str,
    api_key: str,
    timeout_s: float,
) -> DownloadResult:
    work_dir.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + max(30.0, timeout_s)
    timeout = httpx.Timeout(30.0, read=max(30.0, timeout_s))
    headers = {"X-API-Key": api_key, "Accept": "application/json"}
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        content = _parse(client, base_url.rstrip("/"), url, deadline, headers)
        play_url = _pick_play_url(content)
        if not play_url:
            raise FetchDownloadError("解析结果里没有可下载的视频地址。")
        title = content.get("title")
        if not isinstance(title, str) or not title.strip():
            title = None
        else:
            title = title.strip()[:255]
        dest = _download_file(client, play_url, work_dir)
    return DownloadResult(
        video_path=dest,
        title=title,
        subtitle_path=None,
        subtitle_language=None,
    )


def _parse(
    client: httpx.Client,
    base_url: str,
    url: str,
    deadline: float,
    headers: dict[str, str],
) -> dict:
    remaining = max(1.0, deadline - time.monotonic())
    wait = min(_WAIT_SECONDS, int(remaining))
    response = client.post(
        f"{base_url}/api/v1/parse",
        params={"wait": wait},
        json={"url": url},
        headers=headers,
    )
    body = _json_body(response)
    if response.status_code == 202 or _is_pending(body):
        task_id = str((body.get("data") or {}).get("task_id") or "")
        if not task_id:
            raise FetchDownloadError("抖音解析没有返回任务编号。")
        return _poll(client, base_url, task_id, deadline, headers)
    _raise_for_envelope(response, body)
    data = body.get("data")
    if isinstance(data, dict) and data.get("kind"):
        return data
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        return data["data"]
    raise FetchDownloadError("抖音解析没有返回视频信息。")


def _poll(
    client: httpx.Client,
    base_url: str,
    task_id: str,
    deadline: float,
    headers: dict[str, str],
) -> dict:
    while time.monotonic() < deadline:
        response = client.get(f"{base_url}/api/v1/tasks/{task_id}", headers=headers)
        body = _json_body(response)
        _raise_for_envelope(response, body)
        data = body.get("data") if isinstance(body.get("data"), dict) else {}
        state = str(data.get("state") or "")
        if state == "done":
            payload = data.get("data")
            if isinstance(payload, dict):
                _reject_unless_video(payload)
                return payload
            raise FetchDownloadError("抖音解析没有返回视频信息。")
        if state == "failed":
            error = data.get("error") if isinstance(data.get("error"), dict) else {}
            _raise_for_code(str(error.get("code") or ""), str(error.get("message") or ""))
            raise FetchDownloadError("抖音解析失败。")
        time.sleep(min(_POLL_INTERVAL, max(0.0, deadline - time.monotonic())))
    raise FetchDownloadError("抓取超时。请检查解析服务，或在后台「抓取设置」调高超时后重试。")


def _json_body(response: httpx.Response) -> dict:
    try:
        body = response.json()
    except Exception as exc:  # noqa: BLE001
        raise FetchDownloadError(f"抖音解析服务返回了无法识别的内容（HTTP {response.status_code}）。") from exc
    if not isinstance(body, dict):
        raise FetchDownloadError("抖音解析服务返回了无法识别的内容。")
    return body


def _is_pending(body: dict) -> bool:
    data = body.get("data")
    if not isinstance(data, dict) or data.get("kind"):
        return False
    return str(data.get("state") or "") in {"queued", "running"} and bool(data.get("task_id"))


def _raise_for_envelope(response: httpx.Response, body: dict) -> None:
    error = body.get("error") if isinstance(body.get("error"), dict) else None
    if error or response.status_code >= 400 or body.get("success") is False:
        code = str((error or {}).get("code") or "")
        message = str((error or {}).get("message") or "")
        _raise_for_code(code, message or f"HTTP {response.status_code}")


def _raise_for_code(code: str, message: str) -> None:
    if code in _UNAVAILABLE:
        raise FetchDownloadError(
            "抖音解析暂时不可用（身份池耗尽或被风控）。请稍后重试，或到解析服务里检查身份。"
        )
    if code == "INVALID_URL":
        raise FetchDownloadError("这条链接无法识别为抖音视频。")
    if code in {"UNAUTHENTICATED", "FORBIDDEN"}:
        raise FetchDownloadError("抖音解析服务拒绝了 API Key。请到后台「抓取与网络」检查 Key。")
    if code or message:
        raise FetchDownloadError(message or f"抖音解析失败（{code}）。")


def _reject_unless_video(content: dict) -> None:
    kind = str(content.get("kind") or "")
    if kind == "video":
        return
    if kind in {"image_album", "live"}:
        raise FetchDownloadError("这条链接是图文或直播，不能作为视频来源。")
    raise FetchDownloadError("这条链接不能作为视频来源。")


def _pick_play_url(content: dict) -> str | None:
    _reject_unless_video(content)
    media = content.get("media") if isinstance(content.get("media"), dict) else {}
    video = media.get("video") if isinstance(media.get("video"), dict) else {}
    primary = video.get("url") if not video.get("watermark") else None
    if isinstance(primary, str) and primary.startswith(("http://", "https://")):
        return primary
    streams = media.get("streams") if isinstance(media.get("streams"), list) else []
    ranked: list[tuple[int, int, int, str]] = []
    for item in streams:
        if not isinstance(item, dict) or item.get("watermark"):
            continue
        play = item.get("url")
        if not isinstance(play, str) or not play.startswith(("http://", "https://")):
            continue
        fmt = str(item.get("format") or "").lower()
        mp4 = 1 if "mp4" in fmt or play.lower().split("?", 1)[0].endswith(".mp4") else 0
        height = int(item.get("height") or 0)
        bitrate = int(item.get("bitrate") or 0)
        ranked.append((mp4, height, bitrate, play))
    if not ranked:
        return None
    ranked.sort(reverse=True)
    return ranked[0][3]


def _download_file(client: httpx.Client, play_url: str, work_dir: Path) -> Path:
    dest = work_dir / "douyin.mp4"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.douyin.com/",
    }
    try:
        with client.stream("GET", play_url, headers=headers, follow_redirects=True) as resp:
            if resp.status_code >= 400:
                raise FetchDownloadError(f"视频下载失败（HTTP {resp.status_code}）。")
            with dest.open("wb") as out:
                for chunk in resp.iter_bytes():
                    out.write(chunk)
    except FetchDownloadError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise FetchDownloadError(str(exc) or "视频下载失败") from exc
    if not dest.exists() or dest.stat().st_size <= 0:
        raise FetchDownloadError("解析成功，但下载到的视频文件是空的。")
    return dest
