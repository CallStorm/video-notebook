"""按后端分发转写。OpenAI 兼容路径留在 subtitles.transcribe。"""
from __future__ import annotations

from app.llm.config_service import SttResolved
from app.subtitles.srt import Cue
from app.subtitles.transcribe import TranscribeError


async def transcribe_custom(
    stt: SttResolved, audio_path: str, kind: str
) -> tuple[list[Cue], str | None]:
    if kind == "faster_whisper":
        from app.asr.engines import transcribe_faster_whisper

        return await transcribe_faster_whisper(stt, audio_path)
    if kind == "whisper_cpp":
        from app.asr.engines import transcribe_whisper_cpp

        return await transcribe_whisper_cpp(stt, audio_path)
    if kind == "http_whisper_cpp":
        from app.asr.http_server import transcribe_whisper_cpp_server

        return await transcribe_whisper_cpp_server(stt, audio_path)
    raise TranscribeError(f"不支持的语音转写后端 {kind}")
