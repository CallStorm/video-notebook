"""用当前默认聊天模型，根据字幕写一段来源概览。"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.config_service import get_active_llm
from app.llm.providers import make_provider
from app.models.notebook import SubtitleLine, Video
from app.overview_settings.defaults import DEFAULT_OVERVIEW_PROMPT
from app.services.overview_settings import get_overview_settings_row, resolve_prompt

_MAX_TRANSCRIPT_CHARS = 12_000


async def write_overview(
    session: AsyncSession,
    lines: list[SubtitleLine],
    *,
    video: Video | None = None,
) -> str:
    transcript = _transcript(lines)
    if not transcript:
        raise RuntimeError("没有字幕，无法生成概览")

    row = await get_overview_settings_row(session)
    instructions = resolve_prompt(row)
    title = (video.title or "").strip() if video is not None else ""

    # 提示词当作纯说明文字，不 Jinja 渲染；标题仅附加在用户消息里供模型参考
    user_parts = [instructions.strip() or DEFAULT_OVERVIEW_PROMPT, ""]
    if title:
        user_parts.append(f"视频标题：{title}")
        user_parts.append("")
    user_parts.append("字幕内容：")
    user_parts.append(transcript)

    llm = await get_active_llm(session)
    provider = make_provider(
        provider_name=llm.provider,
        api_key=llm.api_key,
        base_url=llm.base_url,
        model_name=llm.model_name,
        params_json=llm.params_json,
    )
    text = await provider.complete(
        "\n".join(user_parts),
        system="你是视频笔记编辑。只输出概览正文，不要开场白或解释。",
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
