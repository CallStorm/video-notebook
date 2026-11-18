"""把音频交给本地（或自建）HTTP ASR。

- protocol=openai（默认）：OpenAI 兼容 `POST {base}/audio/transcriptions`
- protocol=whisper_cpp：whisper.cpp server `POST {base}/inference`
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

from app.asr.engines import cues_from_whisper_cpp_json, finalize_cues
from app.asr.settings import settings_from_stt
from app.llm.config_service import SttResolved
from app.subtitles.cues import distribute, split_subtitle_lines
from app.subtitles.media import probe_duration_ms
from app.subtitles.srt import Cue, parse_srt
from app.subtitles.transcribe import TranscribeError, parse_transcript_body


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
            if cues:
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
    payload = path.read_bytes()
    url = inference_url(settings.endpoint)
    data: dict[str, str] = {"response_format": "verbose_json"}
    if settings.language:
        data["language"] = settings.language
    timeout = httpx.Timeout(settings.timeout_seconds, connect=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.post(
                url,
                headers=auth_headers(settings.api_key),
                data=data,
                files={"file": (path.name, payload, "application/octet-stream")},
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
    cues, language, timestamped = parse_http_transcript(
        response.content, response.headers.get("content-type", "")
    )
    if timestamped:
        return finalize_cues(cues, language or settings.language)
    text = plain_text_from_body(response.content)
    if not text:
        raise TranscribeError("语音转写没有返回文本")
    duration_ms = await asyncio.to_thread(probe_duration_ms, path)
    if duration_ms <= 0:
        duration_ms = 1000
    lines = split_subtitle_lines(text)
    return finalize_cues(distribute(lines, 0, duration_ms), language or settings.language)


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
