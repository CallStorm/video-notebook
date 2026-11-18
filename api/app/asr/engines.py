"""进程内 ASR：faster-whisper，以及 whisper.cpp（CLI 或 pywhispercpp）。

缺依赖时给出安装提示，不在导入本模块时加载模型。
转写结果是带时间轴的 Cue，和线上接口返回 segments 后的形状一致。
"""
from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import tempfile
import threading
from itertools import groupby, pairwise
from pathlib import Path

from app.asr.settings import AsrSettings, settings_from_stt
from app.llm.config_service import SttResolved
from app.subtitles.cues import expand_cues
from app.subtitles.srt import Cue
from app.subtitles.transcribe import TranscribeError

_guard = threading.Lock()
_fw_models: dict[tuple, object] = {}
_fw_locks: dict[tuple, threading.Lock] = {}
_cpp_models: dict[tuple, object] = {}
_cpp_locks: dict[tuple, threading.Lock] = {}


def finalize_cues(cues: list[Cue], language: str | None) -> tuple[list[Cue], str | None]:
    if not cues:
        raise TranscribeError("语音转写没有返回文本")
    lang = language[:16] if language else None
    return expand_cues(cues), lang


def cues_from_ticks(
    rows: list[tuple[int, int, str]],
    *,
    tick_ms: int,
) -> list[Cue]:
    """把 (start, end, text) 按 tick_ms 换成毫秒。faster-whisper 用秒，调用方先换成毫秒再传 1。"""
    cues: list[Cue] = []
    for start_tick, end_tick, text in rows:
        cleaned = text.strip()
        if not cleaned:
            continue
        start_ms = int(start_tick) * tick_ms
        end_ms = int(end_tick) * tick_ms
        if end_ms <= start_ms:
            end_ms = start_ms + 1000
        cues.append(Cue(start_ms=start_ms, end_ms=end_ms, text=cleaned))
    return cues


def _parse_clock(raw: object) -> int:
    text = str(raw or "").strip()
    if not text:
        return 0
    clock, _, frac = text.partition(",")
    if "." in clock and "," not in text:
        clock, _, frac = text.partition(".")
    parts = clock.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
    elif len(parts) == 2:
        hours = "0"
        minutes, seconds = parts
    else:
        return 0
    try:
        millis = int((frac + "000")[:3])
        return (int(hours) * 3600 + int(minutes) * 60 + int(seconds)) * 1000 + millis
    except ValueError:
        return 0


def cues_from_whisper_cpp_json(data: dict) -> tuple[list[Cue], str | None]:
    """解析 whisper.cpp `-oj` 或 /inference 的 JSON。"""
    language = None
    result = data.get("result")
    if isinstance(result, dict) and result.get("language"):
        language = str(result["language"])[:16]
    if data.get("language"):
        language = str(data["language"])[:16]
    rows = data.get("transcription") or data.get("segments") or []
    cues: list[Cue] = []
    if not isinstance(rows, list):
        return [], language
    for row in rows:
        if not isinstance(row, dict):
            continue
        no_speech = row.get("no_speech_prob")
        logprob = row.get("avg_logprob")
        if (
            isinstance(no_speech, (int, float))
            and no_speech > 0.6
            and isinstance(logprob, (int, float))
            and logprob < -1.0
        ):
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        offsets = row.get("offsets") if isinstance(row.get("offsets"), dict) else None
        if offsets is not None and "from" in offsets and "to" in offsets:
            start_ms = int(float(offsets.get("from") or 0))
            end_ms = int(float(offsets.get("to") or 0))
        elif "start" in row or "end" in row:
            start_ms = int(float(row.get("start") or 0) * 1000)
            end_ms = int(float(row.get("end") or 0) * 1000)
        else:
            stamps = row.get("timestamps") if isinstance(row.get("timestamps"), dict) else {}
            start_ms = _parse_clock(stamps.get("from"))
            end_ms = _parse_clock(stamps.get("to"))
        if end_ms <= start_ms:
            end_ms = start_ms + 1000
        cues.append(Cue(start_ms=start_ms, end_ms=end_ms, text=text))
    return _remove_stuck_repetitions(cues), language


def _remove_stuck_repetitions(cues: list[Cue]) -> list[Cue]:
    """Collapse a sustained decoder loop while retaining brief repetitions."""
    clean: list[Cue] = []
    for phrase, group in groupby(cues, key=lambda cue: "".join(
        char for char in cue.text.casefold() if char.isalnum()
    )):
        run = list(group)
        if (
            0 < len(phrase) <= 12
            and len(run) >= 5
            and run[-1].end_ms - run[0].start_ms >= 10_000
            and all(-1000 <= b.start_ms - a.end_ms <= 1000 for a, b in pairwise(run))
        ):
            # Retain the first occurrence in case the phrase was actually spoken.
            clean.append(run[0])
        else:
            clean.extend(run)
    return clean


def _lock_for(bucket: dict[tuple, threading.Lock], key: tuple) -> threading.Lock:
    with _guard:
        lock = bucket.get(key)
        if lock is None:
            lock = threading.Lock()
            bucket[key] = lock
        return lock


def transcribe_faster_whisper_sync(
    settings: AsrSettings, audio_path: str
) -> tuple[list[Cue], str | None]:
    if not settings.model:
        raise TranscribeError("请填写 faster-whisper 模型名或路径")
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise TranscribeError(
            "未安装 faster-whisper。在 api 目录执行：uv sync --extra asr"
        ) from exc

    key = (settings.model, settings.device, settings.compute_type, settings.threads, settings.download_root or "")
    lock = _lock_for(_fw_locks, key)
    with lock:
        model = _fw_models.get(key)
        if model is None:
            kwargs: dict = {
                "device": settings.device,
                "compute_type": settings.compute_type,
            }
            if settings.download_root:
                kwargs["download_root"] = settings.download_root
            if settings.threads:
                kwargs["cpu_threads"] = settings.threads
            try:
                model = WhisperModel(settings.model, **kwargs)
            except Exception as exc:  # noqa: BLE001 — 模型路径或设备错误要写回字幕状态
                raise TranscribeError(f"faster-whisper 加载失败: {exc}") from exc
            _fw_models[key] = model
        try:
            segments, info = model.transcribe(
                audio_path,
                language=settings.language,
                vad_filter=settings.vad_filter,
            )
            rows = [
                (int(float(seg.start) * 1000), int(float(seg.end) * 1000), str(seg.text or ""))
                for seg in segments
            ]
        except Exception as exc:  # noqa: BLE001
            raise TranscribeError(f"faster-whisper 转写失败: {exc}") from exc
    language = getattr(info, "language", None) or settings.language
    return cues_from_ticks(rows, tick_ms=1), str(language)[:16] if language else None


async def transcribe_faster_whisper(
    stt: SttResolved, audio_path: str
) -> tuple[list[Cue], str | None]:
    settings = settings_from_stt(stt)
    cues, language = await asyncio.to_thread(transcribe_faster_whisper_sync, settings, audio_path)
    return finalize_cues(cues, language)


def _pywhispercpp_available() -> bool:
    try:
        import pywhispercpp.model  # noqa: F401
    except ImportError:
        return False
    return True


def resolve_whisper_cpp_engine(config_engine: str | None) -> str:
    engine = (config_engine or "auto").strip().lower()
    if engine in {"cli", "pywhispercpp"}:
        return engine
    if _pywhispercpp_available():
        return "pywhispercpp"
    return "cli"


def resolve_whisper_cli() -> str:
    for name in ("whisper-cli", "whisper-cpp"):
        found = shutil.which(name)
        if found:
            return found
    raise TranscribeError(
        "未找到 whisper-cli。请安装 whisper.cpp 并加入 PATH，"
        "也可以 pip install pywhispercpp。"
    )


def _require_ggml_model(settings: AsrSettings) -> str:
    if not settings.model:
        raise TranscribeError("请填写 whisper.cpp 的 ggml 模型路径（模型名或 config.model_path）")
    path = Path(settings.model).expanduser()
    if not path.is_file():
        raise TranscribeError(f"whisper.cpp 模型文件不存在: {settings.model}")
    return str(path)


def transcribe_whisper_cpp_cli_sync(
    settings: AsrSettings, audio_path: str
) -> tuple[list[Cue], str | None]:
    binary = resolve_whisper_cli()
    model = _require_ggml_model(settings)
    with tempfile.TemporaryDirectory(prefix="vn-asr-") as tmp:
        out_base = str(Path(tmp) / "out")
        cmd = [
            binary,
            "-m",
            model,
            "-f",
            audio_path,
            "-oj",
            "-of",
            out_base,
            "-l",
            settings.language or "auto",
        ]
        if settings.threads:
            cmd.extend(["-t", str(settings.threads)])
        try:
            proc = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                timeout=settings.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise TranscribeError("whisper.cpp 转写超时") from exc
        except OSError as exc:
            raise TranscribeError(f"无法启动 whisper.cpp: {exc}") from exc
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or b"").decode("utf-8", errors="replace")
            raise TranscribeError(f"whisper.cpp 转写失败: {err.strip()[:500]}")
        json_path = Path(out_base + ".json")
        if not json_path.is_file():
            raise TranscribeError("whisper.cpp 没有写出 JSON 结果")
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise TranscribeError("whisper.cpp JSON 无法解析") from exc
    if not isinstance(data, dict):
        raise TranscribeError("whisper.cpp JSON 格式无法识别")
    return cues_from_whisper_cpp_json(data)


def transcribe_pywhispercpp_sync(
    settings: AsrSettings, audio_path: str
) -> tuple[list[Cue], str | None]:
    model_path = _require_ggml_model(settings)
    try:
        from pywhispercpp.model import Model
    except ImportError as exc:
        raise TranscribeError(
            "未安装 pywhispercpp。可改用 whisper-cli，或执行 pip install pywhispercpp。"
        ) from exc
    key = (model_path, settings.threads or 0)
    lock = _lock_for(_cpp_locks, key)
    with lock:
        model = _cpp_models.get(key)
        if model is None:
            kwargs: dict = {}
            if settings.threads:
                kwargs["n_threads"] = settings.threads
            try:
                model = Model(model_path, **kwargs)
            except Exception as exc:  # noqa: BLE001
                raise TranscribeError(f"pywhispercpp 加载失败: {exc}") from exc
            _cpp_models[key] = model
        try:
            segments = model.transcribe(audio_path, language=settings.language or "auto")
        except Exception as exc:  # noqa: BLE001
            raise TranscribeError(f"pywhispercpp 转写失败: {exc}") from exc
    rows: list[tuple[int, int, str]] = []
    for seg in segments:
        # whisper.cpp 的 t0/t1 单位是 10ms。
        rows.append((int(getattr(seg, "t0", 0)), int(getattr(seg, "t1", 0)), str(getattr(seg, "text", "") or "")))
    return cues_from_ticks(rows, tick_ms=10), settings.language


def transcribe_whisper_cpp_sync(
    settings: AsrSettings, audio_path: str, *, engine: str | None = None
) -> tuple[list[Cue], str | None]:
    chosen = resolve_whisper_cpp_engine(engine)
    if chosen == "pywhispercpp":
        return transcribe_pywhispercpp_sync(settings, audio_path)
    return transcribe_whisper_cpp_cli_sync(settings, audio_path)


async def transcribe_whisper_cpp(stt: SttResolved, audio_path: str) -> tuple[list[Cue], str | None]:
    settings = settings_from_stt(stt)
    engine = None
    cfg = stt.config if isinstance(stt.config, dict) else {}
    raw_engine = cfg.get("engine")
    if isinstance(raw_engine, str):
        engine = raw_engine
    cues, language = await asyncio.to_thread(
        transcribe_whisper_cpp_sync, settings, audio_path, engine=engine
    )
    return finalize_cues(cues, language)
