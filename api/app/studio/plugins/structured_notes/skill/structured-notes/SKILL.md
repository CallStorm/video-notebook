---
name: structured-notes
description: 将来源视频/字幕整理成可复查的结构化笔记 JSON（主题、概念、带时间戳要点、论据、结论）。当用户要求结构化笔记、知识卡片、时间轴要点时使用。
---

# 结构化笔记

阅读 `inputs.json` 中的来源与表单字段，写出 `outputs/notes.json` 与约定 `MANIFEST.json`。

## 输出要点

- 精简、好懂、可跳回核对；有可靠时间戳才写 `time`。
- 不要写成长摘要；概念/要点/结论控制体量。
- 严格按 Studio instructions 中的 JSON schema。
