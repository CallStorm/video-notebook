"""SRT 解析与序列化。内嵌字幕和 Whisper 返回的 srt 都走这里。"""
from __future__ import annotations

import re
from dataclasses import dataclass

_TS = re.compile(r"^(?:(\d+):)?(\d+):(\d+)[,.](\d+)$")


@dataclass(frozen=True)
class Cue:
    start_ms: int
    end_ms: int
    text: str


class SrtError(ValueError):
    pass


def parse_srt(text: str) -> list[Cue]:
    """把 SRT 文本拆成 cue。无法识别的块跳过，不抛错。"""
    normalized = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    cues: list[Cue] = []
    for block in re.split(r"\n\s*\n", normalized):
        lines = [line.strip("\n") for line in block.split("\n")]
        lines = [line for line in lines if line.strip()]
        if not lines:
            continue
        time_at = 0
        if "-->" not in lines[0] and len(lines) > 1 and "-->" in lines[1]:
            time_at = 1
        if "-->" not in lines[time_at]:
            continue
        left, right = lines[time_at].split("-->", 1)
        try:
            start_ms = _parse_timestamp(left.strip().split()[0])
            end_ms = _parse_timestamp(right.strip().split()[0])
        except SrtError:
            continue
        body = "\n".join(lines[time_at + 1 :]).strip()
        if not body:
            continue
        if end_ms <= start_ms:
            end_ms = start_ms + 1000
        cues.append(Cue(start_ms=start_ms, end_ms=end_ms, text=body))
    return cues


def format_srt(cues: list[Cue]) -> str:
    blocks: list[str] = []
    for index, cue in enumerate(cues, start=1):
        blocks.append(
            f"{index}\n{_format_timestamp(cue.start_ms)} --> {_format_timestamp(cue.end_ms)}\n{cue.text.strip()}\n"
        )
    return "\n".join(blocks)


def _parse_timestamp(raw: str) -> int:
    match = _TS.match(raw.strip())
    if match is None:
        raise SrtError(f"bad timestamp: {raw}")
    hour_s, minute_s, second_s, frac = match.groups()
    hours = int(hour_s or 0)
    millis = int(frac.ljust(3, "0")[:3])
    return ((hours * 60 + int(minute_s)) * 60 + int(second_s)) * 1000 + millis


def _format_timestamp(ms: int) -> str:
    if ms < 0:
        ms = 0
    hours, rem = divmod(ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"
