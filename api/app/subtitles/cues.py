"""把转写文本切成字幕行，并摊到一段时间上。

有些语音接口（例如硅基流动的 SenseVoice）只回整段文字，没有时间轴。
这时先按音频停顿切开，再在每一段里按句子把时间分下去。
"""
from __future__ import annotations

import re

from app.subtitles.srt import Cue

_SENTENCE_END = re.compile(r"(?<=[。！？!?])")
_CLAUSE_END = re.compile(r"(?<=[，,、；;])")


def split_subtitle_lines(text: str, *, max_chars: int = 40) -> list[str]:
    """按句号切开；一句太长再按逗号折行。"""
    compact = re.sub(r"[ \t]+", " ", text.replace("\r", "")).strip()
    if not compact:
        return []
    sentences = [part.strip() for part in _SENTENCE_END.split(compact) if part.strip()]
    if not sentences:
        sentences = [compact]
    lines: list[str] = []
    for sentence in sentences:
        lines.extend(_wrap_line(sentence, max_chars))
    return [line for line in lines if line]


def expand_cues(cues: list[Cue], *, max_chars: int = 40) -> list[Cue]:
    """已经有时间轴时，只把过长的一条再拆开，时间按字数分。"""
    expanded: list[Cue] = []
    for cue in cues:
        lines = split_subtitle_lines(cue.text, max_chars=max_chars)
        if len(lines) <= 1:
            expanded.append(cue)
            continue
        expanded.extend(distribute(lines, cue.start_ms, cue.end_ms))
    return expanded


def distribute(lines: list[str], start_ms: int, end_ms: int) -> list[Cue]:
    if not lines:
        return []
    span = max(end_ms - start_ms, 200 * len(lines))
    weights = [max(len(line), 1) for line in lines]
    total = sum(weights)
    cues: list[Cue] = []
    consumed = 0
    for index, (line, weight) in enumerate(zip(lines, weights, strict=True)):
        begin = start_ms + span * consumed // total
        consumed += weight
        finish = start_ms + span if index == len(lines) - 1 else start_ms + span * consumed // total
        if finish <= begin:
            finish = begin + 200
        cues.append(Cue(start_ms=begin, end_ms=finish, text=line))
    return cues


def _wrap_line(sentence: str, max_chars: int) -> list[str]:
    if len(sentence) <= max_chars:
        return [sentence]
    pieces = [piece for piece in _CLAUSE_END.split(sentence) if piece]
    if len(pieces) <= 1:
        return [sentence[i : i + max_chars] for i in range(0, len(sentence), max_chars)]
    lines: list[str] = []
    buffer = ""
    for piece in pieces:
        if buffer and len(buffer) + len(piece) > max_chars:
            lines.append(buffer.strip())
            buffer = piece
        else:
            buffer += piece
    if buffer.strip():
        lines.append(buffer.strip())
    return lines
