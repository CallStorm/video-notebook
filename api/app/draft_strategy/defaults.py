"""底稿策略默认常量与内置种子。"""
from __future__ import annotations

from typing import Any

OUTPUT_SCHEMA: dict[str, Any] = {
    "theme": "一句话主题",
    "concepts": [{"term": "术语", "definition": "一句话解释"}],
    "points": [
        {
            "text": "要点文案",
            "time": "MM:SS 或 HH:MM:SS（可选）",
            "source_hint": "来源锚点（可选）",
            "evidence": "原句短引（可选）",
            "example": "生活/典故短例子（1–2 句，必填）",
            "example_kind": "life|allusion|work|other（可选）",
        }
    ],
    "takeaways": ["可执行收获 / 行动项"],
    "open_questions": ["遗留问题（可选，可空数组）"],
    "meta": {
        "strategy_id": "策略 id",
        "model": "所用模型引用",
        "sources": ["来源标识列表"],
    },
}

OUTPUT_SCHEMA_INSTRUCTION = """你必须只输出一个 JSON 对象（不要 Markdown 围栏、不要开场白），字段如下（只写有内容的；数组键不可省略，可为空数组）：
{
  "theme": "一句话主题",
  "concepts": [{"term": "术语", "definition": "一句话解释"}],
  "points": [{"text": "要点", "time": "MM:SS", "evidence": "短引（可选）", "example": "生活或典故短例子", "example_kind": "life"}],
  "takeaways": ["可执行收获"],
  "open_questions": []
}
硬性规则（违反则视为失败输出）：
1. 有可靠时间戳就写 time（MM:SS 或 HH:MM:SS），没有就省略 time，禁止编造。
2. 每一条 points[i] 都必须有非空字符串字段 example：用 1–2 句生活场景或典故帮助理解要点（例如「例：就像开车只盯后视镜会错过眼前风景」这种），禁止把原句字幕塞进 example，禁止留空、禁止省略该字段。
3. example_kind 尽量填写：life / allusion / work / other。
4. evidence 仍可写原句短引（可选）；example 与 evidence 不是同一字段。
5. takeaways 要可执行，禁止空话。
6. 字符串内若需引号，优先用中文「」或转义为 \"；禁止在 JSON 字符串里直接写未转义的英文双引号，对象/数组元素之间必须有逗号。"""

DEFAULT_PREFIX = """你是视频知识底稿编辑。目标：从字幕/来源抽出可勾选、可跳播、可复习的知识底稿，而不是长摘要。

硬性规则：
1. 忠于来源：只写材料里有依据的内容，禁止臆造、禁止扩写成教材。
2. 时间锚点：要点尽量带字幕时间戳与原句短引；没有可靠时间就省略，不要编。
3. 输出契约：必须输出符合系统给出的 JSON schema 的对象；不要 Markdown 代码围栏。
4. 语言：默认简体中文；若用户另有语言要求则跟随。
5. 体量：宁少勿滥，删空话与重复。"""

KIND_LABELS: dict[str, str] = {
    "deep_read": "精读",
    "action": "行动",
    "glossary": "词典",
    "compare": "对比",
    "custom": "自定义",
}

BUILTIN_STRATEGIES: list[dict[str, Any]] = [
    {
        "name": "deep_read",
        "title": "精读底稿",
        "description": "主题 + 概念 + 带时间戳论点 + 证据短引 + takeaways。日常一条视频学完带走。",
        "kind": "deep_read",
        "apply_default": True,
        "enabled": True,
        "suggested_model": "inherit",
        "min_sources": 1,
        "prompt": """任务：生成「精读底稿」。

重点：
- theme：一句话说清整段材料在讲什么。
- concepts：3–8 个关键术语，各一句解释。
- points：5–12 条按时间或逻辑排列的要点；尽量带 time 与 evidence；每条必须带 example（生活/典故短例子 1–2 句）。
- takeaways：3–7 条可勾选的可执行收获。
- open_questions：若有未决问题可列，否则 []。

禁止：大段转述字幕、空洞鸡汤、与主题无关枝节。""",
    },
    {
        "name": "action_list",
        "title": "行动清单",
        "description": "偏可落地改动：问题 → 建议 → 影响 → 下一步；时间戳对准原话。",
        "kind": "action",
        "apply_default": False,
        "enabled": True,
        "suggested_model": "inherit",
        "min_sources": 1,
        "prompt": """任务：生成「行动清单」型知识底稿。

重点：
- theme：这份材料要推动什么行动/决策。
- concepts：只保留与落地相关的术语（可少）。
- points：每条尽量写成「问题/现状 → 建议动作」，并带 time + evidence + example（落地场景短例子）。
- takeaways：必须是可执行下一步（谁/做什么/注意什么），3–8 条。
- open_questions：落地前还需确认的问题。

禁止：纯概念科普、无法执行的空泛总结。""",
    },
    {
        "name": "glossary",
        "title": "概念词典",
        "description": "术语表为主：定义 + 首次出现时间 + 易混对比。适合课与长演讲。",
        "kind": "glossary",
        "apply_default": False,
        "enabled": True,
        "suggested_model": "inherit",
        "min_sources": 1,
        "prompt": """任务：生成「概念词典」型知识底稿。

重点：
- theme：这份材料的知识领域一句话。
- concepts：尽量完整的关键术语表（可到 8–15）；definition 用材料里的含义，勿抄百科。
- points：补充易混对比、首次出现语境；尽量标 time；每条带 example（易记的生活/典故对照）。
- takeaways：如何记住/区分这些概念的实用提示（可少）。
- open_questions：材料未讲清的术语疑问。

禁止：离开材料的百科扩写。""",
    },
    {
        "name": "compare_read",
        "title": "对比精读",
        "description": "多来源：共识 / 冲突 / 各自独有；冲突项尽量双时间戳。勾选 ≥2 个来源时推荐。",
        "kind": "compare",
        "apply_default": False,
        "enabled": True,
        "suggested_model": "inherit",
        "min_sources": 2,
        "prompt": """任务：生成「对比精读」底稿（输入含多个来源时）。

重点：
- theme：对比在回答什么共同问题。
- concepts：跨来源共享的关键概念。
- points：明确标出「共识 / 冲突 / 独有」；冲突处尽量给双方 time 或在 text 里写清来源；每条带 example。
- takeaways：读完应如何取舍或组合各方观点。
- open_questions：仍无法裁定的分歧。

若实际只有一个来源：降级为精读，并在 open_questions 说明「仅单来源，未能对比」。""",
    },
]
