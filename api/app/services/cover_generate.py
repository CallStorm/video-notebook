"""按名称 + 可选描述生成笔记本/集合封面（文生图或 SVG token）。"""
from __future__ import annotations

import hashlib
import json
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, BadRequestError, NotFoundError, ServiceUnavailableError
from app.llm.config_service import get_active_cover_image_llm, get_active_logo_llm
from app.llm.image_generate import generate_image_bytes
from app.llm.providers import make_provider
from app.services import cover_settings as cover_cfg
from app.services.cover_url import expand_cover_url, put_cover_image

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
# 色板索引见 _PALETTE_BANK。具体场景规则放前面，避免被「管理/笔记」等宽泛词抢先。
_THEME_RULES: list[tuple[tuple[str, ...], tuple[int, int], str, tuple[str, ...], str]] = [
    (
        ("新能源", "电动", "汽车", "充电", "能源", "电池", "电车", "EV", "ev"),
        (3, 5),
        "ev",
        ("hero", "split", "accent"),
        "",
    ),
    (
        ("工地", "施工", "建筑", "土木", "工程现场", "基建", "钢筋", "混凝土"),
        (14, 14),
        "nature",
        ("bands", "hero", "split"),
        "",
    ),
    (
        ("党建", "党史", "红色", "思政", "党校"),
        (9, 10),
        "creative",
        ("badge", "hero", "frame"),
        "",
    ),
    (
        ("合同", "造价", "预算", "审计", "会计", "招投标", "结算"),
        (13, 15),
        "finance",
        ("bands", "accent", "frame"),
        "",
    ),
    (
        ("科技", "编程", "代码", "AI", "算法", "数据", "数字", "互联网", "软件", "技术", "芯片"),
        (0, 4),
        "tech",
        ("accent", "frame", "split"),
        "",
    ),
    (
        ("经济", "财经", "金融", "财政", "投资", "股市", "理财", "商业", "营销", "职场", "财务"),
        (13, 15),
        "finance",
        ("bands", "accent", "frame"),
        "",
    ),
    (
        ("自然", "健康", "运动", "环保", "植物", "旅行", "户外", "生态"),
        (5, 7),
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
        ("学习", "教育", "考试", "课程", "笔记", "知识", "阅读", "书", "培训"),
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


def match_theme(text: str) -> tuple[tuple[int, int], str, tuple[str, ...], str] | None:
    """优先匹配更长的关键词，减少「管理/笔记」等宽泛词误伤。"""
    hay = text or ""
    hay_cf = hay.casefold()
    best: tuple[int, tuple[tuple[int, int], str, tuple[str, ...], str]] | None = None
    for keys, rng, motif, layouts, label in _THEME_RULES:
        for key in keys:
            hit = key in hay or key.casefold() in hay_cf
            if not hit:
                continue
            score = len(key)
            cand = (rng, motif, layouts, label)
            if best is None or score > best[0]:
                best = (score, cand)
    return best[1] if best else None


def style_from_title(title: str, description: str | None = None) -> dict:
    """名称(+描述)驱动的确定性样式：同输入稳定、不同输入差异明显，并尽量语义相关。"""
    trimmed = (title or "").strip() or "未命名"
    desc = (description or "").strip()
    combined = f"{trimmed}\n{desc}" if desc else trimmed
    seed = _title_seed(combined)
    theme = match_theme(combined)

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


def _parse_style(raw: str, *, fallback: dict) -> dict | None:
    """解析模型 JSON；无法解析时返回 None（由调用方决定是否回退）。"""
    text = (raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    match = _JSON_OBJ.search(text)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None

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


def _finalize_style(
    style: dict,
    *,
    base: dict,
    title: str,
    description: str = "",
    force_keyword_motif: bool,
) -> dict:
    out = dict(style)
    combined = f"{title}\n{description}" if description else title
    # 若模型仍退回「万能蓝」且语义不需要蓝：只替换色板，保留模型 layout/motif/pattern
    if _looks_generic_blue(out) and not _text_wants_blue(combined):
        out["a"] = base["a"]
        out["b"] = base["b"]
        out["c"] = base["c"]
        out["ink"] = base["ink"]
        out["mist"] = base["mist"]
        if out["layout"] not in _LAYOUTS:
            out["layout"] = base["layout"]
        if out["motif"] not in _MOTIFS:
            out["motif"] = base["motif"]
        if out["pattern"] not in _PATTERNS:
            out["pattern"] = base["pattern"]
    if force_keyword_motif:
        theme = match_theme(combined)
        if theme is not None:
            _, motif, layout_pool, _label = theme
            out["motif"] = motif
            out["label"] = ""
            if out["layout"] not in layout_pool:
                out["layout"] = layout_pool[0] if layout_pool else base["layout"]
    else:
        out["label"] = ""
    return out


async def generate_cover(
    session: AsyncSession,
    *,
    title: str,
    description: str | None = None,
    mode: str | None = None,
) -> dict:
    trimmed = (title or "").strip()
    if not trimmed:
        raise BadRequestError("名称不能为空")
    if len(trimmed) > 255:
        raise BadRequestError("名称过长")
    desc = (description or "").strip()
    if len(desc) > 2000:
        raise BadRequestError("描述过长")

    settings_row = await cover_cfg.get_cover_settings_row(session)
    override = (mode or "").strip().lower()
    if override in ("image", "svg"):
        mode = override
    else:
        mode = cover_cfg.resolve_mode(settings_row)
    if mode == "image":
        return await _generate_cover_image(
            session, settings_row=settings_row, title=trimmed, description=desc
        )
    return await _generate_cover_svg(
        session, settings_row=settings_row, title=trimmed, description=desc
    )


async def _generate_cover_image(
    session: AsyncSession,
    *,
    settings_row,
    title: str,
    description: str,
) -> dict:
    system_prompt = cover_cfg.resolve_image_system_prompt(settings_row)
    user_template = cover_cfg.resolve_image_user_prompt(settings_row)
    size = cover_cfg.resolve_image_size(settings_row)
    prompt = cover_cfg.render_image_prompt(
        system_prompt, user_template, title=title, description=description
    )
    try:
        llm = await get_active_cover_image_llm(session)
    except NotFoundError as exc:
        raise BadRequestError(
            "未配置「封面文生图」模型：请到管理后台 → 模型配置，为「封面文生图」绑定出图模型。"
            "MiniMax 请新增模型名 image-01（同一凭证即可）；"
            "OpenAI 兼容网关可用 FLUX / Kolors / dall-e。不要绑聊天模型当出图模型。"
        ) from exc
    try:
        raw, content_type = await generate_image_bytes(
            api_key=llm.api_key,
            base_url=llm.base_url,
            model_name=llm.model_name,
            prompt=prompt,
            size=size,
            provider=getattr(llm, "provider", None),
        )
    except (BadRequestError, ServiceUnavailableError, AppError):
        raise
    except Exception as exc:
        msg = str(exc).strip() or exc.__class__.__name__
        raise ServiceUnavailableError(f"封面文生图失败：{msg}") from exc

    if not raw:
        raise ServiceUnavailableError("封面文生图返回空内容")

    stored = put_cover_image(data=raw, content_type=content_type)
    return {
        "cover_url": expand_cover_url(stored) or stored,
        "layout": "image",
        "motif": "image",
        "pattern": "image",
        "a": "#000000",
        "b": "#000000",
        "c": "#000000",
        "ink": "#FFFFFF",
        "mist": "#888888",
        "label": "",
        "storage_key": stored,
    }


async def _generate_cover_svg(
    session: AsyncSession,
    *,
    settings_row,
    title: str,
    description: str,
) -> dict:
    trimmed = title
    desc = description
    system_prompt = cover_cfg.resolve_system_prompt(settings_row)
    user_template = cover_cfg.resolve_user_prompt(settings_row)
    temperature = cover_cfg.resolve_temperature(settings_row)
    force_keyword = cover_cfg.resolve_force_keyword_motif(settings_row)
    fallback_on_error = cover_cfg.resolve_fallback_on_error(settings_row)

    base = style_from_title(trimmed, desc)
    rich_soften = 24
    try:
        from app.cover_settings.defaults import DEFAULT_RICH_DESC_SOFTEN_CHARS

        rich_soften = int(DEFAULT_RICH_DESC_SOFTEN_CHARS)
    except Exception:
        rich_soften = 24
    if desc and len(desc) >= rich_soften:
        force_keyword = False

    def _ok(style: dict) -> dict:
        final = _finalize_style(
            style,
            base=base,
            title=trimmed,
            description=desc,
            force_keyword_motif=force_keyword,
        )
        token = encode_cover_token(final)
        return {
            "cover_url": token,
            **{
                k: final[k]
                for k in (
                    "layout",
                    "motif",
                    "pattern",
                    "a",
                    "b",
                    "c",
                    "ink",
                    "mist",
                    "label",
                )
            },
        }

    try:
        llm = await get_active_logo_llm(session)
        provider = make_provider(
            provider_name=llm.provider,
            api_key=llm.api_key,
            base_url=llm.base_url,
            model_name=llm.model_name,
            params_json=llm.params_json,
        )
        user_msg = cover_cfg.render_user_prompt(
            user_template, title=trimmed, description=desc
        )
        raw = await provider.complete(
            user_msg,
            system=system_prompt,
            max_tokens=280,
            temperature=temperature,
        )
        parsed = _parse_style(raw, fallback=base)
        if parsed is None:
            raise ServiceUnavailableError("封面模型返回无法解析，请稍后重试")
        return _ok(parsed)
    except ServiceUnavailableError:
        if fallback_on_error:
            return _ok(dict(base))
        raise
    except AppError:
        if fallback_on_error:
            return _ok(dict(base))
        raise
    except Exception as exc:
        if fallback_on_error:
            return _ok(dict(base))
        msg = str(exc).strip() or exc.__class__.__name__
        raise ServiceUnavailableError(f"封面生成失败：{msg}") from exc



def _looks_generic_blue(style: dict) -> bool:
    """仅当主色+雾色都是常见万能蓝青时才判定，避免误伤合理的科技蓝。"""
    b = (style.get("b") or "").upper().lstrip("#")
    mist = (style.get("mist") or "").upper().lstrip("#")
    a = (style.get("a") or "").upper().lstrip("#")
    blues = {"2563EB", "3B82F6", "0EA5E9", "38BDF8", "0284C7", "0891B2", "22D3EE", "60A5FA", "93C5FD"}
    navy = {"0B1F4A", "1E3A8A", "172554", "082F49"}
    b_blue = b in blues
    mist_blue = mist in blues
    a_navy = a in navy
    # 经典「深蓝底 + 亮蓝主色」万能模板
    return (b_blue and mist_blue) or (a_navy and b_blue)


def _text_wants_blue(text: str) -> bool:
    keys = (
        "科技", "编程", "代码", "AI", "算法", "数据", "数字", "互联网", "软件", "技术",
        "芯片", "新能源", "汽车", "能源", "电动",
    )
    return any(k in (text or "") for k in keys)

