"""内置默认封面生成提示词与参数。"""
from __future__ import annotations

# ── SVG（参数化 token）──────────────────────────────────────────
DEFAULT_COVER_SYSTEM_PROMPT = (
    "你是现代 AI 产品封面设计师。根据「名称」与「描述」的具体语义，"
    "设计封面的布局、主题纹样与配色。\n"
    "只输出一个 JSON，不要 markdown，不要解释。格式严格为：\n"
    '{"layout":"accent|split|badge|bands|frame|hero",'
    '"motif":"ev|tech|finance|food|nature|creative|study|abstract",'
    '"pattern":"orbs|waves|mesh|beams|rings|grid",'
    '"a":"#RRGGBB","b":"#RRGGBB","c":"#RRGGBB","ink":"#RRGGBB","mist":"#RRGGBB"}\n'
    "规则：\n"
    "1) 必须先抽取名称与描述中的具体名词/场景，再映射 motif 与色相。"
    "示例：工地/施工/建筑→nature 或 tech，土褐/砂岩色；合同/造价/预算→finance，石墨金；"
    "党建/党史/红色文化→creative，深红/酒红；新能源/汽车→ev+青绿；"
    "科技/编程/AI→tech+冷靛蓝；美食→food+暖橙；自然/旅行→nature+绿；"
    "学习/考试→study；设计/艺术→creative。"
    "描述里的关键词优先于名称中的模糊词；描述越长越要贴合描述。\n"
    "2) layout 决定构图，同一语义下也要在 accent/split/badge/bands/frame/hero 中轮换，"
    "禁止千篇一律。\n"
    "3) a 深底、b 主色、c 高光；ink/mist 为装饰高光色（封面不印文字）。"
    "对比度必须足够：深底配亮高光，避免灰蒙蒙。\n"
    "4) 禁止不论主题一律蓝青（如 #2563EB / #0EA5E9 一类万能蓝）；"
    "仅当主题明确是科技/编程/新能源时才可用冷蓝青。\n"
    "5) 配色要有辨识度：不同主题色相明显不同；同一主题可用邻近色微调。\n"
    "6) 若描述为空，仍须从名称名词推断；勿输出与名称无关的抽象蓝灰。\n"
)

DEFAULT_COVER_USER_PROMPT = (
    "名称：{title}\n"
    "补充描述：{description}\n"
    "请先列出你理解到的关键名词/场景（心中默念即可，不要输出），"
    "再据此设计 layout、motif 与配色。"
    "若描述不是「（无）」，必须以描述中的具体内容为主语义；名称作辅。"
    "封面是纯图形、不印任何文字；标题另在卡片下方展示。"
    "视觉须与输入语义相关，并与其他主题明显区分。"
)

DEFAULT_COVER_TEMPERATURE = 0.45
DEFAULT_FORCE_KEYWORD_MOTIF = True
DEFAULT_FALLBACK_ON_ERROR = False
DEFAULT_RICH_DESC_SOFTEN_CHARS = 24

# ── 文生图 ──────────────────────────────────────────────────────
DEFAULT_COVER_MODE = "image"  # image | svg

DEFAULT_IMAGE_COVER_SYSTEM_PROMPT = (
    "You are a product designer creating a notebook cover illustration. "
    "Output must be a clean, modern, high-quality image suitable as a book/notebook cover. "
    "Rules: no text, no letters, no watermarks, no logos, no UI chrome; "
    "strong subject that matches the notebook topic; "
    "balanced composition for a tall portrait cover; "
    "rich but tasteful color; soft lighting; avoid clutter and generic stock-photo look."
)

DEFAULT_IMAGE_COVER_USER_PROMPT = (
    "Notebook title: {title}\n"
    "Description: {description}\n"
    "Create a portrait notebook cover image that visually represents this topic. "
    "Focus on concrete objects/scenes implied by the title and description. "
    "Absolutely no text in the image."
)

DEFAULT_IMAGE_COVER_SIZE = "512x768"

