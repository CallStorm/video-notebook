"""用后台配置的语音转文字模型转写本地音频。

只支持 OpenAI 兼容的 /audio/transcriptions（provider=openai 或 whisper）。
模型若能返回 segments / srt，就用它的时间轴。
像硅基流动 SenseVoice 这种只回整段 text 的，按停顿把音频切开再转写，
然后在每一段里按句子把时间分下去。
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.llm.config_service import SttResolved
from app.subtitles.cues import distribute, expand_cues, split_subtitle_lines
from app.subtitle_slice_settings.runtime import get_settings_fresh
from app.subtitles.media import (
    build_speech_ranges,
    cut_slice,
    probe_duration_ms,
)
from app.subtitles.srt import Cue, parse_srt

logger = logging.getLogger(__name__)

_WHISPER_SIZE_NAMES = {
    "tiny",
    "base",
    "small",
    "medium",
    "large",
    "large-v1",
    "large-v2",
    "large-v3",
}


class TranscribeError(RuntimeError):
    pass


@dataclass
class ParsedTranscript:
    cues: list[Cue]
    language: str | None
    timestamped: bool
    text: str


def resolve_model_name(name: str | None) -> str:
    """后台若填的是模型大小（large-v3），公开 Whisper API 只认 whisper-1。"""
    cleaned = (name or "").strip()
    if not cleaned or cleaned in _WHISPER_SIZE_NAMES:
        return "whisper-1"
    return cleaned


async def transcribe_file(stt: SttResolved, audio_path: str) -> tuple[list[Cue], str | None]:
    if stt.provider not in ("openai", "whisper"):
        raise TranscribeError(f"当前语音转文字供应商 {stt.provider} 还不支持自动转写")
    if not stt.api_key:
        raise TranscribeError("语音转文字凭证没有 API Key")

    path = Path(audio_path)
    duration_ms = await asyncio.to_thread(probe_duration_ms, path)
    if duration_ms <= 0:
        duration_ms = 1000

    timeout = httpx.Timeout(600.0, connect=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        # 先拿一小段探测。能返回时间轴就整段转；否则不要先把整集传上去白跑一遍。
        probe_ms = min(duration_ms, 12_000)
        probe_path = path
        if duration_ms > probe_ms + 3_000:
            probe_path = await asyncio.to_thread(cut_slice, path, 0, probe_ms)
        try:
            probed = await _request_transcript(client, stt, probe_path, want_timestamps=True)
        finally:
            if probe_path != path:
                probe_path.unlink(missing_ok=True)

        if probed.timestamped and probe_path == path:
            return expand_cues(probed.cues), probed.language
        if probed.timestamped:
            full = await _request_transcript(client, stt, path, want_timestamps=True)
            if full.timestamped:
                return expand_cues(full.cues), full.language or probed.language

        if duration_ms <= probe_ms + 3_000 and probed.text:
            return distribute(split_subtitle_lines(probed.text), 0, duration_ms), probed.language

        slice_cfg = get_settings_fresh()
        ranges = await asyncio.to_thread(
            build_speech_ranges,
            path,
            duration_ms,
            max_ms=slice_cfg.max_slice_ms,
            min_ms=slice_cfg.min_slice_ms,
            silence_noise_db=slice_cfg.silence_noise_db,
            silence_min_duration_s=slice_cfg.silence_min_duration_s,
            min_silence_for_cut_ms=slice_cfg.min_silence_for_cut_ms,
        )
        if not ranges:
            ranges = [(0, duration_ms)]
        logger.info(
            "chunked transcription model=%s slices=%s duration_ms=%s max_slice_ms=%s",
            stt.model_name,
            len(ranges),
            duration_ms,
            slice_cfg.max_slice_ms,
        )
        return await _transcribe_ranges(
            client, stt, path, ranges, fallback_language=probed.language
        )


async def _request_transcript(
    client: httpx.AsyncClient,
    stt: SttResolved,
    audio_path: Path,
    *,
    want_timestamps: bool,
) -> ParsedTranscript:
    formats: list[dict[str, str]] = (
        [
            {"response_format": "verbose_json", "timestamp_granularities[]": "segment"},
            {"response_format": "json"},
        ]
        if want_timestamps
        else [{"response_format": "json"}]
    )
    payload = audio_path.read_bytes()
    filename = audio_path.name
    last_error = "语音转写失败"
    empty_ok: ParsedTranscript | None = None
    for fields in formats:
        response = await _post_audio(client, stt, payload, filename, fields)
        if response.status_code in (401, 403):
            raise TranscribeError("语音转写鉴权失败，请检查后台 API Key")
        if response.status_code >= 400:
            last_error = _http_error(response)
            logger.info(
                "transcription attempt %s failed: %s",
                fields.get("response_format"),
                last_error,
            )
            continue
        parsed = parse_transcript_body(response.content, fields["response_format"])
        if parsed.timestamped or parsed.text:
            # verbose_json 若只回了 text，说明对方忽略了时间轴，不必再把同一段传一次。
            return parsed
        # SenseVoice 等对静音/噪声片会回 HTTP 200 + text=""。切片场景应跳过，不能整集失败。
        empty_ok = parsed
    if empty_ok is not None:
        return empty_ok
    raise TranscribeError(last_error)


async def _transcribe_ranges(
    client: httpx.AsyncClient,
    stt: SttResolved,
    src: Path,
    ranges: list[tuple[int, int]],
    *,
    fallback_language: str | None,
) -> tuple[list[Cue], str | None]:
    """按时间范围边切边转，避免一次物化上百个临时文件。"""
    semaphore = asyncio.Semaphore(3)
    language = fallback_language

    async def one(start_ms: int, end_ms: int) -> tuple[list[Cue], str | None]:
        async with semaphore:
            slice_path = await asyncio.to_thread(cut_slice, src, start_ms, end_ms)
            try:
                if slice_path.stat().st_size == 0:
                    return [], None
                parsed = await _request_transcript(
                    client, stt, slice_path, want_timestamps=False
                )
                if not parsed.text and not parsed.cues:
                    return [], parsed.language
                if parsed.timestamped:
                    shifted = [
                        Cue(
                            start_ms=cue.start_ms + start_ms,
                            end_ms=cue.end_ms + start_ms,
                            text=cue.text,
                        )
                        for cue in parsed.cues
                    ]
                    return expand_cues(shifted), parsed.language
                lines = split_subtitle_lines(parsed.text)
                return distribute(lines, start_ms, end_ms), parsed.language
            finally:
                slice_path.unlink(missing_ok=True)

    parts = await asyncio.gather(*(one(start, end) for start, end in ranges))
    cues: list[Cue] = []
    for part_cues, part_language in parts:
        cues.extend(part_cues)
        if language is None and part_language:
            language = part_language
    if not cues:
        raise TranscribeError("语音转写没有返回文本")
    return cues, language


async def _post_audio(
    client: httpx.AsyncClient,
    stt: SttResolved,
    payload: bytes,
    filename: str,
    fields: dict[str, str],
) -> httpx.Response:
    base = (stt.base_url or "https://api.openai.com/v1").rstrip("/")
    url = f"{base}/audio/transcriptions"
    model = resolve_model_name(stt.model_name)
    last: httpx.Response | None = None
    for attempt in range(4):
        response = await client.post(
            url,
            headers={"Authorization": f"Bearer {stt.api_key}"},
            data={"model": model, **fields},
            files={"file": (filename, payload, "application/octet-stream")},
        )
        last = response
        if response.status_code not in (429, 500, 502, 503):
            return response
        await asyncio.sleep(1.5 * (attempt + 1))
    assert last is not None
    return last


def parse_transcript_body(body: bytes, response_format: str) -> ParsedTranscript:
    if response_format == "srt":
        cues = parse_srt(body.decode("utf-8", errors="replace"))
        text = "\n".join(cue.text for cue in cues)
        return ParsedTranscript(cues=cues, language=None, timestamped=bool(cues), text=text)
    try:
        data = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise TranscribeError("语音转写返回的不是 JSON") from exc
    if not isinstance(data, dict):
        raise TranscribeError("语音转写返回格式无法识别")
    language = data.get("language")
    lang = str(language)[:16] if language else None
    cues: list[Cue] = []
    for segment in data.get("segments") or []:
        if not isinstance(segment, dict):
            continue
        text = str(segment.get("text") or "").strip()
        if not text:
            continue
        start = int(float(segment.get("start") or 0) * 1000)
        end = int(float(segment.get("end") or 0) * 1000)
        if end <= start:
            end = start + 1000
        cues.append(Cue(start_ms=start, end_ms=end, text=text))
    if cues:
        return ParsedTranscript(
            cues=cues,
            language=lang,
            timestamped=True,
            text="\n".join(cue.text for cue in cues),
        )
    text = str(data.get("text") or "").strip()
    return ParsedTranscript(cues=[], language=lang, timestamped=False, text=text)


def _http_error(response: httpx.Response) -> str:
    snippet = response.text.strip().replace("\n", " ")[:300]
    if not snippet:
        return f"语音转写 HTTP {response.status_code}"
    return f"语音转写 HTTP {response.status_code}: {snippet}"
