"""内置默认概览提示词（参考 Open Notebook Simple Summary 思路）。"""
from __future__ import annotations

DEFAULT_OVERVIEW_PROMPT = (
    "优先选择能交代主题、关键事实或结论的字幕。"
    "跳过重复和无关片段。根据素材长短选择，内容较少时保留少量关键句。"
)

DEFAULT_AUTO_GENERATE_AFTER_SUBTITLE = True
