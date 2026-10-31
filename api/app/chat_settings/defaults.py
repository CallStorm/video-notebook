"""对话设置默认值（可被环境变量 / DB 覆盖）。"""
from __future__ import annotations

# 最近 N 轮用户+助手成对；与历史硬编码 _HISTORY_LIMIT=8 对齐。
DEFAULT_CHAT_HISTORY_LIMIT = 8
MIN_CHAT_HISTORY_LIMIT = 2
MAX_CHAT_HISTORY_LIMIT = 20

# 对话上下文字符预算（字幕全文 + 笔记 + 问题 + 历史）。勾选字幕全文超限时报错不截断。
DEFAULT_MAX_CONTEXT_CHARS = 60_000
MIN_MAX_CONTEXT_CHARS = 10_000
MAX_MAX_CONTEXT_CHARS = 500_000
