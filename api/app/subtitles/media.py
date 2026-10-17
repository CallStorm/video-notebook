"""用 ffprobe / ffmpeg 抽内嵌字幕和音频。没装 ffmpeg 时返回 None，交给 ASR 兜底。"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.subtitles.srt import Cue, parse_srt

logger = logging.getLogger(__name__)

# OpenAI 语音转写接口的单文件上限。
MAX_AUDIO_BYTES = 25 * 1024 * 1024
# 没有停顿时，硬切的最长一段。再长，句子时间就会漂。
MAX_SLICE_MS = 18_000
MIN_SLICE_MS = 600

_SILENCE_START = re.compile(r"silence_start: (\d+(?:\.\d+)?)")
_SILENCE_END = re.compile(r"silence_end: (\d+(?:\.\d+)?)")


@dataclass(frozen=True)
class AudioSlice:
    start_ms: int
    end_ms: int
    path: Path


class MediaError(RuntimeError):
    pass


def extract_embedded_cues(path: Path) -> tuple[list[Cue], str | None] | None:
    """有内嵌字幕轨就抽成 cue。没有、或工具不可用，返回 None。"""
    if shutil.which("ffprobe") is None or shutil.which("ffmpeg") is None:
        return None
    if not path.is_file():
        return None
    try:
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "s",
                "-show_entries",
                "stream=index:stream_tags=language",
                "-of",
                "json",
                str(path),
            ],
            check=False,
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("ffprobe subtitle scan failed: %s", exc)
        return None
    if probe.returncode != 0:
        return None
    try:
        payload = json.loads(probe.stdout.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return None
    streams = payload.get("streams") or []
    if not streams:
        return None
    language = (streams[0].get("tags") or {}).get("language")
    try:
        extracted = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(path),
                "-map",
                "0:s:0",
                "-f",
                "srt",
                "pipe:1",
            ],
            check=False,
            capture_output=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("ffmpeg subtitle extract failed: %s", exc)
        return None
    if extracted.returncode != 0 or not extracted.stdout.strip():
        logger.info("embedded subtitle extract produced nothing: %s", extracted.stderr[-400:])
        return None
    cues = parse_srt(extracted.stdout.decode("utf-8", errors="replace"))
    if not cues:
        return None
    lang = str(language)[:16] if language else None
    return cues, lang


def prepare_audio(path: Path) -> Path:
    """准备送给语音转写的文件。优先抽成 16kHz 单声道 mp3，避开 25MB 上限。

    返回的路径如果是临时文件，调用方负责删除。原文件直接可用时返回原路径。
    """
    if not path.is_file():
        raise MediaError("视频文件不在本地存储中")
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        if path.stat().st_size <= MAX_AUDIO_BYTES:
            return path
        raise MediaError("视频超过 25MB，且本机没有 ffmpeg，无法先抽出音频")
    handle, name = tempfile.mkstemp(suffix=".mp3")
    # mkstemp 打开了 fd，ffmpeg 会自己写这个路径。
    os.close(handle)
    out = Path(name)
    try:
        proc = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-b:a",
                "64k",
                str(out),
            ],
            check=False,
            capture_output=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired as exc:
        out.unlink(missing_ok=True)
        raise MediaError("抽出音频超时") from exc
    except OSError as exc:
        out.unlink(missing_ok=True)
        raise MediaError(f"抽出音频失败: {exc}") from exc
    if proc.returncode != 0 or not out.is_file() or out.stat().st_size == 0:
        stderr = proc.stderr.decode("utf-8", errors="replace")[-500:]
        out.unlink(missing_ok=True)
        if path.stat().st_size <= MAX_AUDIO_BYTES:
            logger.info("ffmpeg audio extract failed, sending original file: %s", stderr)
            return path
        raise MediaError("没有可用音轨，无法转写")
    return out


def probe_duration_ms(path: Path) -> int:
    if shutil.which("ffprobe") is None or not path.is_file():
        return 0
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=False,
        capture_output=True,
        timeout=30,
    )
    if proc.returncode != 0:
        return 0
    try:
        return max(0, int(float(proc.stdout.decode().strip()) * 1000))
    except ValueError:
        return 0


def detect_silences(path: Path) -> list[tuple[int, int]]:
    """找出静音区间（毫秒）。失败时当没有停顿，后面会按固定长度切开。"""
    if shutil.which("ffmpeg") is None:
        return []
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-i",
                str(path),
                "-af",
                "silencedetect=noise=-32dB:d=0.3",
                "-f",
                "null",
                "-",
            ],
            check=False,
            capture_output=True,
            timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("silencedetect failed: %s", exc)
        return []
    stderr = proc.stderr.decode("utf-8", errors="replace")
    starts = [int(float(value) * 1000) for value in _SILENCE_START.findall(stderr)]
    ends = [int(float(value) * 1000) for value in _SILENCE_END.findall(stderr)]
    silences: list[tuple[int, int]] = []
    for index, start in enumerate(starts):
        end = ends[index] if index < len(ends) else start
        if end > start:
            silences.append((start, end))
    return silences


def speech_ranges(
    duration_ms: int,
    silences: list[tuple[int, int]],
    *,
    max_ms: int = MAX_SLICE_MS,
    min_ms: int = MIN_SLICE_MS,
) -> list[tuple[int, int]]:
    """尽量在静音处切开，但每一段不超过 max_ms，避免请求次数爆炸。"""
    if duration_ms <= 0:
        return []
    cuts = [0, duration_ms]
    for start, end in silences:
        if end - start < 200:
            continue
        middle = (start + end) // 2
        if 0 < middle < duration_ms:
            cuts.append(middle)
    cuts = sorted(set(cuts))

    ranges: list[tuple[int, int]] = []
    window_start = 0
    last_fit = 0
    for point in cuts[1:]:
        if point - window_start <= max_ms:
            last_fit = point
            continue
        if last_fit - window_start >= min_ms:
            ranges.append((window_start, last_fit))
            window_start = last_fit
        else:
            ranges.append((window_start, min(duration_ms, window_start + max_ms)))
            window_start = ranges[-1][1]
        while point - window_start > max_ms:
            ranges.append((window_start, window_start + max_ms))
            window_start += max_ms
        last_fit = point
    if duration_ms - window_start >= 200:
        ranges.append((window_start, duration_ms))
    elif ranges and window_start < duration_ms:
        prev_start, _prev_end = ranges[-1]
        ranges[-1] = (prev_start, duration_ms)
    return ranges


def build_speech_ranges(path: Path, duration_ms: int) -> list[tuple[int, int]]:
    return speech_ranges(duration_ms, detect_silences(path))


def cut_slice(src: Path, start_ms: int, end_ms: int) -> Path:
    handle, name = tempfile.mkstemp(suffix=".mp3")
    os.close(handle)
    dest = Path(name)
    try:
        _cut_audio(src, start_ms, end_ms, dest)
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return dest


def materialize_slices(src: Path, ranges: list[tuple[int, int]]) -> list[AudioSlice]:
    slices: list[AudioSlice] = []
    try:
        for start, end in ranges:
            dest = cut_slice(src, start, end)
            slices.append(AudioSlice(start_ms=start, end_ms=end, path=dest))
    except Exception:
        for item in slices:
            item.path.unlink(missing_ok=True)
        raise
    return slices


def _cut_audio(src: Path, start_ms: int, end_ms: int, dest: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise MediaError("没有 ffmpeg，无法按时间切开音频")
    proc = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-ss",
            f"{start_ms / 1000:.3f}",
            "-to",
            f"{end_ms / 1000:.3f}",
            "-i",
            str(src),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-b:a",
            "64k",
            str(dest),
        ],
        check=False,
        capture_output=True,
        timeout=120,
    )
    if proc.returncode != 0 or not dest.is_file() or dest.stat().st_size == 0:
        stderr = proc.stderr.decode("utf-8", errors="replace")[-400:]
        raise MediaError(f"切开音频失败: {stderr}")
