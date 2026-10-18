"""按名称用 LLM 生成单个 emoji 图标。"""
from __future__ import annotations

import re
import unicodedata

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError
from app.llm.config_service import get_active_logo_llm
from app.llm.providers import make_provider

_SYSTEM = (
    "你是图标设计师。根据用户给出的名称，只输出一个最贴切的 emoji。"
    "不要输出任何文字、标点、引号或解释。只输出那一个 emoji。"
)

# Broad emoji / pictograph ranges + ZWJ / variation selectors / keycaps / flags.
_EMOJI_CHUNK = re.compile(
    "(?:"
    "[\U0001F1E0-\U0001F1FF]{2}"  # flag
    "|"
    "[0-9#*]\uFE0F?\u20E3"  # keycap
    "|"
    "(?:"
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U00002300-\U000023FF]"
    "[\U0000FE0F\U0000200D\U0001F3FB-\U0001F3FF\U0001F9B0-\U0001F9B3]*"
    ")+"
    ")"
)


def _is_symbolish(ch: str) -> bool:
    cat = unicodedata.category(ch)
    return cat.startswith("S") or cat in ("So", "Sk") or ord(ch) > 0x1F000


def extract_emoji(raw: str) -> str | None:
    """从模型回复里取出第一个合法 emoji（长度 ≤16）。"""
    text = (raw or "").strip().strip("\"'`").strip()
    if not text:
        return None
    match = _EMOJI_CHUNK.search(text)
    if match:
        icon = match.group(0)
        if icon and len(icon) <= 16:
            return icon
    # Fallback: first non-ascii symbol grapheme cluster (naive)
    if len(text) <= 16 and any(_is_symbolish(c) for c in text) and not any(
        c.isascii() and c.isalnum() for c in text
    ):
        return text
    return None


async def generate_icon(session: AsyncSession, name: str) -> str:
    trimmed = (name or "").strip()
    if not trimmed:
        raise BadRequestError("名称不能为空")
    if len(trimmed) > 255:
        raise BadRequestError("名称过长")

    llm = await get_active_logo_llm(session)
    provider = make_provider(
        provider_name=llm.provider,
        api_key=llm.api_key,
        base_url=llm.base_url,
        model_name=llm.model_name,
        params_json=llm.params_json,
    )
    raw = await provider.complete(
        f"名称：{trimmed}",
        system=_SYSTEM,
        max_tokens=32,
        temperature=0.7,
    )
    icon = extract_emoji(raw)
    if not icon:
        raise BadRequestError("模型没有返回可用的 emoji，请重试")
    return icon
