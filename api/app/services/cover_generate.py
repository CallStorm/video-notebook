"""按名称 + 描述用 LLM 生成笔记本封面样式参数。"""
from __future__ import annotations

import json
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError
from app.llm.config_service import get_active_logo_llm
from app.llm.providers import make_provider

_PATTERNS = ("orbs", "waves", "mesh", "beams")

_SYSTEM = (
    "你是现代 AI 产品封面设计师。根据笔记本名称与描述，输出明亮、通透、有电光感的抽象封面配色。\n"
    "只输出一行 JSON，不要 markdown，不要解释。格式严格为：\n"
    '{"pattern":"orbs|waves|mesh|beams","a":"#RRGGBB","b":"#RRGGBB",'
    '"c":"#RRGGBB","ink":"#RRGGBB","mist":"#RRGGBB"}\n'
    "配色规则（必须遵守）：\n"
    "1) 整体要亮：禁止黑、炭黑、墨绿、深紫等沉闷底色；不要灰蒙蒙的低饱和色。\n"
    "2) a = 渐变起点，中等偏亮的主色（如 #1D4ED8 / #0EA5E9 / #0891B2 / #4F46E5），"
    "亮度适中，绝不能接近纯黑。\n"
    "3) b = 中间高光色，鲜明电光蓝/青/靛蓝（如 #3B82F6 / #22D3EE / #38BDF8 / #818CF8）。\n"
    "4) c = 最浅高光，接近天空色或冰晶白蓝（如 #DBEAFE / #CFFAFE / #E0E7FF / #F0FDFA）。\n"
    "5) ink = 近白文字色（#F8FAFC 或 #FFFFFF），保证对比清晰。\n"
    "6) mist = 明亮装饰色，饱和度高、偏浅（如 #60A5FA / #2DD4BF / #A5B4FC）。\n"
    "7) 可按主题微调色相（经济→蓝金倾向的亮蓝；自然→青绿；科技→电光蓝），"
    "但始终保持明亮、干净、高级，像 NotebookLM / Linear 产品封面，而不是夜景海报。\n"
    "8) 每次生成可略有不同，但必须满足以上亮度要求。"
)

_HEX = re.compile(r"^#?[0-9A-Fa-f]{6}$")
_JSON_OBJ = re.compile(r"\{[^{}]*\}")


def _norm_hex(raw: str, fallback: str) -> str:
    s = (raw or "").strip()
    if not _HEX.match(s):
        return fallback
    return s if s.startswith("#") else f"#{s}"


def _parse_style(raw: str) -> dict:
    text = (raw or "").strip()
    # strip ```json fences if any
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    match = _JSON_OBJ.search(text)
    if not match:
        raise BadRequestError("模型没有返回可用的封面样式，请重试")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise BadRequestError("模型返回的封面 JSON 无法解析") from exc

    pattern = str(data.get("pattern", "orbs")).lower().strip()
    if pattern not in _PATTERNS:
        pattern = "orbs"

    return {
        "pattern": pattern,
        "a": _norm_hex(str(data.get("a", "")), "#1D4ED8"),
        "b": _norm_hex(str(data.get("b", "")), "#38BDF8"),
        "c": _norm_hex(str(data.get("c", "")), "#DBEAFE"),
        "ink": _norm_hex(str(data.get("ink", "")), "#FFFFFF"),
        "mist": _norm_hex(str(data.get("mist", "")), "#7DD3FC"),
    }


def encode_cover_token(style: dict) -> str:
    """紧凑 token，写入 notebooks.cover_url（≤512）。"""
    parts = [
        "gen:v2",
        style["pattern"],
        style["a"].lstrip("#"),
        style["b"].lstrip("#"),
        style["c"].lstrip("#"),
        style["ink"].lstrip("#"),
        style["mist"].lstrip("#"),
    ]
    return ":".join(parts)


async def generate_cover(
    session: AsyncSession,
    *,
    title: str,
    description: str | None = None,
) -> dict:
    trimmed = (title or "").strip()
    if not trimmed:
        raise BadRequestError("名称不能为空")
    if len(trimmed) > 255:
        raise BadRequestError("名称过长")
    desc = (description or "").strip()
    if len(desc) > 2000:
        raise BadRequestError("描述过长")

    llm = await get_active_logo_llm(session)
    provider = make_provider(
        provider_name=llm.provider,
        api_key=llm.api_key,
        base_url=llm.base_url,
        model_name=llm.model_name,
        params_json=llm.params_json,
    )
    user_msg = f"名称：{trimmed}"
    if desc:
        user_msg += f"\n描述：{desc}"
    else:
        user_msg += "\n描述：（无）"

    raw = await provider.complete(
        user_msg,
        system=_SYSTEM,
        max_tokens=200,
        temperature=0.9,
    )
    style = _parse_style(raw)
    token = encode_cover_token(style)
    return {"cover_url": token, **style}
