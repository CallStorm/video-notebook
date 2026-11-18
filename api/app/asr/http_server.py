"""把音频交给本地（或自建）HTTP ASR。

- protocol=openai（默认）：OpenAI 兼容 `POST {base}/audio/transcriptions`
- protocol=whisper_cpp：whisper.cpp server `POST {base}/inference`
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

import httpx

from app.asr.engines import cues_from_whisper_cpp_json, finalize_cues
from app.asr.settings import settings_from_stt
from app.llm.config_service import SttResolved
from app.subtitles.cues import distribute, split_subtitle_lines
from app.subtitles.media import MediaError, cut_slice, probe_duration_ms
from app.subtitles.srt import Cue, parse_srt
from app.subtitles.transcribe import TranscribeError, parse_transcript_body

logger = logging.getLogger(__name__)

# A single Whisper segment can span a VAD join when its start lands just
# before the discarded pause. Retry these outliers on shorter source windows.
_LONG_CUE_MS = 40_000
_RETRY_WINDOW_MS = 20_000


def inference_url(endpoint: str) -> str:
    base = endpoint.strip().rstrip("/")
    if base.endswith("/inference"):
        return base
    return f"{base}/inference"


def auth_headers(api_key: str | None) -> dict[str, str]:
    if not api_key:
        return {}
    return {"Authorization": f"Bearer {api_key}"}


def parse_http_transcript(body: bytes, content_type: str) -> tuple[list[Cue], str | None, bool]:
    """返回 cues、语言、是否自带时间轴。时间轴优先，否则只留整段文本对应的空 cues。"""
    sniffed = content_type.lower()
    text = body.decode("utf-8", errors="replace").strip()
    if "application/json" in sniffed or text.startswith("{") or text.startswith("["):
        try:
            data = json.loads(text or "{}")
        except json.JSONDecodeError as exc:
            raise TranscribeError("本地 ASR 服务返回的不是 JSON") from exc
        if isinstance(data, dict):
            cues, language = cues_from_whisper_cpp_json(data)
            timestamp_arrays = [
                data[key] for key in ("transcription", "segments") if isinstance(data.get(key), list)
            ]
            if cues or any(timestamp_arrays) or (timestamp_arrays and not data.get("text")):
                # A timestamped response can contain zero cues after VAD or filtering.
                return cues, language, True
            parsed = parse_transcript_body(body, "json")
            if parsed.timestamped:
                return parsed.cues, parsed.language, True
            if parsed.text:
                return [], parsed.language, False
            return [], parsed.language, False
        raise TranscribeError("本地 ASR 服务返回格式无法识别")
    cues = parse_srt(text)
    if cues:
        return cues, None, True
    if text:
        return [], None, False
    return [], None, False


async def transcribe_whisper_cpp_server(
    stt: SttResolved, audio_path: str
) -> tuple[list[Cue], str | None]:
    settings = settings_from_stt(stt)
    if not settings.endpoint:
        raise TranscribeError("本地 ASR 服务需要填写 endpoint URL（凭证的 Base URL）")
    path = Path(audio_path)
    url = inference_url(settings.endpoint)
    data: dict[str, str] = {"response_format": "verbose_json"}
    if settings.language:
        data["language"] = settings.language
    timeout = httpx.Timeout(settings.timeout_seconds, connect=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async def request(audio: Path) -> httpx.Response:
            try:
                response = await client.post(
                    url,
                    headers=auth_headers(settings.api_key),
                    data=data,
                    files={"file": (audio.name, audio.read_bytes(), "application/octet-stream")},
                )
            except httpx.HTTPError as exc:
                raise TranscribeError(f"无法连接本地 ASR 服务: {exc}") from exc
            if response.status_code in (401, 403):
                raise TranscribeError("本地 ASR 服务鉴权失败，请检查 API Key")
            if response.status_code >= 400:
                snippet = response.text.strip().replace("\n", " ")[:300]
                raise TranscribeError(
                    f"本地 ASR 服务 HTTP {response.status_code}"
                    + (f": {snippet}" if snippet else "")
                )
            return response

        response = await request(path)
        cues, language, timestamped = parse_http_transcript(
            response.content, response.headers.get("content-type", "")
        )
        if timestamped:
            cues = await _repair_long_cues(path, cues, request)
            return finalize_cues(cues, language or settings.language)
    text = plain_text_from_body(response.content)
    if not text:
        raise TranscribeError("语音转写没有返回文本")
    duration_ms = await asyncio.to_thread(probe_duration_ms, path)
    if duration_ms <= 0:
        duration_ms = 1000
    lines = split_subtitle_lines(text)
    return finalize_cues(distribute(lines, 0, duration_ms), language or settings.language)



async def _repair_long_cues(
    path: Path,
    cues: list[Cue],
    request: Callable[[Path], Awaitable[httpx.Response]],
) -> list[Cue]:
    if all(cue.end_ms - cue.start_ms <= _LONG_CUE_MS for cue in cues):
        return cues
    duration_ms = await asyncio.to_thread(probe_duration_ms, path)
    if duration_ms <= 0:
        return cues

    repaired: list[Cue] = []
    for cue in cues:
        if cue.end_ms - cue.start_ms <= _LONG_CUE_MS:
            repaired.append(cue)
            continue

        replacement: list[Cue] = []
        try:
            stop = min(cue.end_ms, duration_ms)
            for start in range(max(0, cue.start_ms), stop, _RETRY_WINDOW_MS):
                end = min(start + _RETRY_WINDOW_MS, stop)
                clip = await asyncio.to_thread(cut_slice, path, start, end)
                try:
                    response = await request(clip)
                    segments, _, timestamped = parse_http_transcript(
                        response.content, response.headers.get("content-type", "")
                    )
                finally:
                    clip.unlink(missing_ok=True)
                if not timestamped:
                    raise TranscribeError("切片转写未返回时间轴")
                for segment in segments:
                    begin = start + max(0, segment.start_ms)
                    finish = min(start + segment.end_ms, end)
                    if finish > begin:
                        replacement.append(Cue(begin, finish, segment.text))
        except (MediaError, OSError, TranscribeError) as exc:
            # Keep the original cue if the server cannot repair the entire interval.
            logger.warning("whisper.cpp cue timing repair failed at %d ms: %s", cue.start_ms, exc)
            repaired.append(cue)
        else:
            repaired.extend(replacement)
    return repaired


def plain_text_from_body(body: bytes) -> str:
    """测试和纯文本响应共用：JSON 取 text，否则整段当文本。"""
    text = body.decode("utf-8", errors="replace").strip()
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return text
        if isinstance(data, dict):
            return str(data.get("text") or "").strip()
    return text
