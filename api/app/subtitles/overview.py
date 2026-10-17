"""用当前默认聊天模型，根据字幕写一段来源概览。"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.config_service import get_active_llm
from app.llm.providers import make_provider
from app.models.notebook import SubtitleLine

_MAX_TRANSCRIPT_CHARS = 12_000


async def write_overview(session: AsyncSession, lines: list[SubtitleLine]) -> str:
    transcript = _transcript(lines)
    if not transcript:
        raise RuntimeError("没有字幕，无法生成概览")
    llm = await get_active_llm(session)
    provider = make_provider(
        provider_name=llm.provider,
        api_key=llm.api_key,
        base_url=llm.base_url,
        model_name=llm.model_name,
        params_json=llm.params_json,
    )
    text = await provider.complete(
        "根据下面的视频字幕，写一段中文概览，150到300字。"
        "概括主题和关键内容，不要使用小标题或项目符号。\n\n" + transcript,
        system="你是视频笔记编辑。只输出概览正文。",
        max_tokens=800,
    )
    cleaned = text.strip()
    if not cleaned:
        raise RuntimeError("模型没有返回概览")
    return cleaned[:4000]


def _transcript(lines: list[SubtitleLine]) -> str:
    parts: list[str] = []
    total = 0
    for line in lines:
        piece = (line.text or "").strip()
        if not piece:
            continue
        parts.append(piece)
        total += len(piece)
        if total >= _MAX_TRANSCRIPT_CHARS:
            break
    return "\n".join(parts)
