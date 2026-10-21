"""对话设置默认值（可被环境变量 / DB 覆盖）。"""
from __future__ import annotations

# 最近 N 轮用户+助手成对；与历史硬编码 _HISTORY_LIMIT=8 对齐。
DEFAULT_CHAT_HISTORY_LIMIT = 8
MIN_CHAT_HISTORY_LIMIT = 2
MAX_CHAT_HISTORY_LIMIT = 20
