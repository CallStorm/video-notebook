"""按名称 + 可选描述生成笔记本/集合封面样式 token（gen:v3）。"""
from __future__ import annotations

import hashlib
import json
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError
from app.llm.config_service import get_active_logo_llm
from app.llm.providers import make_provider

_PATTERNS = ("orbs", "waves", "mesh", "beams", "rings", "grid")
_LAYOUTS = ("accent", "split", "badge", "bands", "frame", "hero")
_MOTIFS = ("ev", "tech", "finance", "food", "nature", "creative", "study", "abstract")

# 多种色系，避免全是蓝青。按名称 hash / 关键词选。
_PALETTE_BANK: list[dict[str, str]] = [
    {"a": "#0B1F4A", "b": "#2563EB", "c": "#93C5FD", "ink": "#F8FAFC", "mist": "#60A5FA"},
    {"a": "#1E1B4B", "b": "#4F46E5", "c": "#A5B4FC", "ink": "#EEF2FF", "mist": "#818CF8"},
    {"a": "#312E81", "b": "#6366F1", "c": "#C7D2FE", "ink": "#EEF2FF", "mist": "#A5B4FC"},
    {"a": "#042F2E", "b": "#0D9488", "c": "#5EEAD4", "ink": "#F0FDFA", "mist": "#2DD4BF"},
    {"a": "#083344", "b": "#0891B2", "c": "#67E8F9", "ink": "#ECFEFF", "mist": "#22D3EE"},
    {"a": "#14532D", "b": "#059669", "c": "#6EE7B7", "ink": "#ECFDF5", "mist": "#34D399"},
    {"a": "#1A2E05", "b": "#65A30D", "c": "#BEF264", "ink": "#F7FEE7", "mist": "#A3E635"},
    {"a": "#7C2D12", "b": "#EA580C", "c": "#FDBA74", "ink": "#FFF7ED", "mist": "#FB923C"},
    {"a": "#78350F", "b": "#D97706", "c": "#FCD34D", "ink": "#FFFBEB", "mist": "#FBBF24"},
    {"a": "#881337", "b": "#E11D48", "c": "#FDA4AF", "ink": "#FFF1F2", "mist": "#FB7185"},
    {"a": "#701A75", "b": "#C026D3", "c": "#F0ABFC", "ink": "#FDF4FF", "mist": "#E879F9"},
    {"a": "#4C1D95", "b": "#7C3AED", "c": "#DDD6FE", "ink": "#F5F3FF", "mist": "#A78BFA"},
    {"a": "#3B0764", "b": "#9333EA", "c": "#E9D5FF", "ink": "#FAF5FF", "mist": "#C084FC"},
    {"a": "#0F172A", "b": "#334155", "c": "#94A3B8", "ink": "#F8FAFC", "mist": "#64748B"},
    {"a": "#1C1917", "b": "#A16207", "c": "#FDE68A", "ink": "#FFFBEB", "mist": "#EAB308"},
    {"a": "#082F49", "b": "#0284C7", "c": "#7DD3FC", "ink": "#F0F9FF", "mist": "#38BDF8"},
]

# 关键词 → (色板区间, motif, 推荐 layout 池)
_THEME_RULES: list[tuple[tuple[str, ...], tuple[int, int], str, tuple[str, ...], str]] = [
    (
        ("新能源", "电动", "汽车", "充电", "能源", "电池", "电车", "EV", "ev"),
        (3, 5),
        "ev",
        ("hero", "split", "accent"),
        "",
    ),
    (
        ("科技", "编程", "代码", "AI", "算法", "数据", "数字", "互联网", "软件", "技术", "工程", "芯片"),
        (0, 4),
        "tech",
        ("accent", "frame", "split"),
        "",
    ),
    (
        ("经济", "财经", "金融", "财政", "投资", "股市", "理财", "商业", "营销", "职场", "管理", "财务"),
        (13, 14),
        "finance",
        ("bands", "accent", "frame"),
        "",
    ),
    (
        ("自然", "健康", "运动", "环保", "植物", "旅行", "户外", "生态"),
        (5, 6),
        "nature",
        ("hero", "split", "bands"),
        "",
    ),
    (
        ("美食", "餐饮", "料理", "烹饪", "探店", "食谱"),
        (7, 8),
        "food",
        ("badge", "hero", "bands"),
        "",
    ),
    (
        ("创意", "设计", "艺术", "音乐", "电影", "娱乐", "游戏"),
        (11, 12),
        "creative",
        ("badge", "split", "frame"),
        "",
    ),
    (
        ("学习", "教育", "考试", "课程", "笔记", "知识", "阅读", "书"),
        (0, 2),
        "study",
        ("accent", "frame", "bands"),
        "",
    ),
    (
        ("情感", "恋爱", "生活", "日常", "人物", "故事"),
        (9, 10),
        "abstract",
        ("badge", "hero", "bands"),
        "",
    ),
]

_SYSTEM = (
    "你是现代 AI 产品封面设计师。根据「名称」语义设计封面的布局、主题纹样与配色。\n"
    "只输出一个 JSON，不要 markdown，不要解释。格式严格为：\n"
    '{"layout":"accent|split|badge|bands|frame|hero",'
    '"motif":"ev|tech|finance|food|nature|creative|study|abstract",'
    '"pattern":"orbs|waves|mesh|beams|rings|grid",'
    '"a":"#RRGGBB","b":"#RRGGBB","c":"#RRGGBB","ink":"#RRGGBB","mist":"#RRGGBB"}\n'
    "规则：\n"
    "1) 先理解名称含义再选型。新能源/汽车→ev+青绿；经济/金融→finance+石墨金；"
    "科技→tech+冷靛蓝；美食→food+暖橙；自然→nature+绿；学习→study；创意→creative。\n"
    "2) layout 决定构图，不同主题尽量选不同 layout，禁止千篇一律。\n"
    "3) a 深底 b 主色 c 高光 ink/mist 装饰高光色（封面不印文字，仅作图形配色）。对比要足。\n"
    "4) 禁止不论名称一律蓝青。\n"
)

_HEX = re.compile(r"^#?[0-9A-Fa-f]{6}$")
_JSON_OBJ = re.compile(r"\{[^{}]*\}")


def _norm_hex(raw: str, fallback: str) -> str:
    s = (raw or "").strip()
    if not _HEX.match(s):
        return fallback
    return s if s.startswith("#") else f"#{s}"


def _title_seed(title: str) -> int:
    digest = hashlib.sha256(title.strip().encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def match_theme(title: str) -> tuple[tuple[int, int], str, tuple[str, ...], str] | None:
    for keys, rng, motif, layouts, label in _THEME_RULES:
        for key in keys:
            if key.casefold() in title.casefold() or key in title:
                return rng, motif, layouts, label
    return None


def style_from_title(title: str) -> dict:
    """纯名称驱动的确定性样式：同名稳定、不同名差异明显，并尽量语义相关。"""
    trimmed = (title or "").strip() or "未命名"
    seed = _title_seed(trimmed)
    theme = match_theme(trimmed)

    if theme is not None:
        rng, motif, layout_pool, label = theme
        lo, hi = rng
        span = max(1, hi - lo + 1)
        palette = _PALETTE_BANK[lo + (seed // 7) % span]
        layout = layout_pool[seed % len(layout_pool)]
    else:
        palette = _PALETTE_BANK[seed % len(_PALETTE_BANK)]
        motif = "abstract"
        layout = _LAYOUTS[seed % len(_LAYOUTS)]
        label = ""
        # 轻微扰动，避免无关键词时撞车
        if (seed % 5) == 0:
            palette = _PALETTE_BANK[(seed // 11) % len(_PALETTE_BANK)]

    pattern = _PATTERNS[seed % len(_PATTERNS)]
    # 同主题不同名：再扰动 pattern
    if theme is not None:
        pattern = _PATTERNS[(seed // 3) % len(_PATTERNS)]

    return {
        "layout": layout,
        "motif": motif,
        "pattern": pattern,
        "a": palette["a"],
        "b": palette["b"],
        "c": palette["c"],
        "ink": palette["ink"],
        "mist": palette["mist"],
        "label": "",
    }


def _parse_style(raw: str, *, fallback: dict) -> dict:
    text = (raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    match = _JSON_OBJ.search(text)
    if not match:
        return dict(fallback)
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return dict(fallback)

    pattern = str(data.get("pattern", fallback["pattern"])).lower().strip()
    if pattern not in _PATTERNS:
        pattern = fallback["pattern"]
    layout = str(data.get("layout", fallback.get("layout", "accent"))).lower().strip()
    if layout not in _LAYOUTS:
        layout = fallback.get("layout", "accent")
    motif = str(data.get("motif", fallback.get("motif", "abstract"))).lower().strip()
    if motif not in _MOTIFS:
        motif = fallback.get("motif", "abstract")

    return {
        "layout": layout,
        "motif": motif,
        "pattern": pattern,
        "a": _norm_hex(str(data.get("a", "")), fallback["a"]),
        "b": _norm_hex(str(data.get("b", "")), fallback["b"]),
        "c": _norm_hex(str(data.get("c", "")), fallback["c"]),
        "ink": _norm_hex(str(data.get("ink", "")), fallback["ink"]),
        "mist": _norm_hex(str(data.get("mist", "")), fallback["mist"]),
        "label": fallback.get("label", ""),
    }


def encode_cover_token(style: dict) -> str:
    """紧凑 token，写入 cover_url（≤512）。gen:v3 含 layout+motif。"""
    parts = [
        "gen:v3",
        style.get("layout", "accent"),
        style.get("motif", "abstract"),
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

    base = style_from_title(trimmed)
    style = dict(base)

    try:
        llm = await get_active_logo_llm(session)
        provider = make_provider(
            provider_name=llm.provider,
            api_key=llm.api_key,
            base_url=llm.base_url,
            model_name=llm.model_name,
            params_json=llm.params_json,
        )
        user_msg = (
            f"名称：{trimmed}\n"
            "请根据这个名称的含义设计封面布局(layout)、主题纹样(motif)与配色。"
            "封面是纯图形、不印任何文字；标题另在卡片下方展示。视觉须与名称语义相关，并与其他主题明显区分。"
        )
        if desc:
            user_msg += f"\n补充描述：{desc}"

        raw = await provider.complete(
            user_msg,
            system=_SYSTEM,
            max_tokens=280,
            temperature=1.0,
        )
        style = _parse_style(raw, fallback=base)
        # 若模型仍退回「万能蓝」且名称没有科技语义，用名称底稿替换主色，保留模型 layout/motif/pattern
        if _looks_generic_blue(style) and not _title_wants_blue(trimmed):
            style = {
                **base,
                "layout": style["layout"] if style["layout"] in _LAYOUTS else base["layout"],
                "motif": style["motif"] if style["motif"] in _MOTIFS else base["motif"],
                "pattern": style["pattern"] if style["pattern"] in _PATTERNS else base["pattern"],
            }
        # 关键词命中时，强制 motif 贴合语义（LLM 偶发跑偏）
        theme = match_theme(trimmed)
        if theme is not None:
            _, motif, layout_pool, label = theme
            style["motif"] = motif
            style["label"] = ""
            if style["layout"] not in layout_pool:
                style["layout"] = base["layout"]
    except Exception:
        style = dict(base)

    token = encode_cover_token(style)
    return {"cover_url": token, **{k: style[k] for k in ("layout", "motif", "pattern", "a", "b", "c", "ink", "mist", "label")}}


def _looks_generic_blue(style: dict) -> bool:
    b = (style.get("b") or "").upper()
    mist = (style.get("mist") or "").upper()
    blues = ("2563EB", "3B82F6", "0EA5E9", "38BDF8", "0284C7", "0891B2", "22D3EE", "60A5FA")
    return any(x in b or x in mist for x in blues)


def _title_wants_blue(title: str) -> bool:
    keys = (
        "科技", "编程", "代码", "AI", "算法", "数据", "数字", "互联网", "软件", "技术",
        "学习", "教育", "知识", "新能源", "汽车", "能源",
    )
    return any(k in title for k in keys)
