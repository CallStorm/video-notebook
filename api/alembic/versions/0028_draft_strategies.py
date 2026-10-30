"""draft strategy settings + strategies tables and builtin seeds."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0028_draft_strategies"
down_revision: str | None = "0027_studio_agent_null"
branch_labels: str | None = None
depends_on: str | None = None

DEFAULT_PREFIX = """你是视频知识底稿编辑。目标：从字幕/来源抽出可勾选、可跳播、可复习的知识底稿，而不是长摘要。

硬性规则：
1. 忠于来源：只写材料里有依据的内容，禁止臆造、禁止扩写成教材。
2. 时间锚点：要点尽量带字幕时间戳与原句短引；没有可靠时间就省略，不要编。
3. 输出契约：必须输出符合系统给出的 JSON schema 的对象；不要 Markdown 代码围栏。
4. 语言：默认简体中文；若用户另有语言要求则跟随。
5. 体量：宁少勿滥，删空话与重复。"""

BUILTINS = [
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
- points：5–12 条按时间或逻辑排列的要点；尽量带 time 与 evidence（原句短引）。
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
- points：每条尽量写成「问题/现状 → 建议动作」，并带 time + evidence。
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
- points：补充易混对比、首次出现语境；尽量标 time。
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
- points：明确标出「共识 / 冲突 / 独有」；冲突处尽量给双方 time 或在 text 里写清来源。
- takeaways：读完应如何取舍或组合各方观点。
- open_questions：仍无法裁定的分歧。

若实际只有一个来源：降级为精读，并在 open_questions 说明「仅单来源，未能对比」。""",
    },
]


def upgrade() -> None:
    op.create_table(
        "draft_strategy_settings",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("default_prefix", sa.Text(), nullable=False),
        sa.Column("default_model_ref", sa.String(length=32), nullable=False, server_default="claude_code"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "draft_strategies",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("apply_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("suggested_model", sa.String(length=32), nullable=False, server_default="inherit"),
        sa.Column("min_sources", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name", name="uq_draft_strategies_name"),
    )
    op.create_index("ix_draft_strategies_kind", "draft_strategies", ["kind"])

    settings = sa.table(
        "draft_strategy_settings",
        sa.column("id", sa.Integer),
        sa.column("default_prefix", sa.Text),
        sa.column("default_model_ref", sa.String),
    )
    op.bulk_insert(
        settings,
        [{"id": 1, "default_prefix": DEFAULT_PREFIX, "default_model_ref": "claude_code"}],
    )

    strategies = sa.table(
        "draft_strategies",
        sa.column("name", sa.String),
        sa.column("title", sa.String),
        sa.column("description", sa.Text),
        sa.column("kind", sa.String),
        sa.column("prompt", sa.Text),
        sa.column("apply_default", sa.Boolean),
        sa.column("enabled", sa.Boolean),
        sa.column("suggested_model", sa.String),
        sa.column("min_sources", sa.Integer),
        sa.column("is_builtin", sa.Boolean),
    )
    rows = []
    for b in BUILTINS:
        rows.append(
            {
                "name": b["name"],
                "title": b["title"],
                "description": b["description"],
                "kind": b["kind"],
                "prompt": b["prompt"],
                "apply_default": b["apply_default"],
                "enabled": b["enabled"],
                "suggested_model": b["suggested_model"],
                "min_sources": b["min_sources"],
                "is_builtin": True,
            }
        )
    op.bulk_insert(strategies, rows)


def downgrade() -> None:
    op.drop_index("ix_draft_strategies_kind", table_name="draft_strategies")
    op.drop_table("draft_strategies")
    op.drop_table("draft_strategy_settings")
