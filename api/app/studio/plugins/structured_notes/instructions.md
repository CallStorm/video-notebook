- 主文件是结构化笔记 JSON，路径 `outputs/notes.json`（UTF-8）。
- 也可用 Markdown 备选：`outputs/notes.md`（仅当无法写 JSON 时）。
- `outputs/MANIFEST.json` 必须是这一份，字段名不能改：
  {"status":"success","title":"笔记标题","artifacts":[{"role":"main","path":"outputs/notes.json","mime":"application/json"}]}
- JSON 字段（只写有内容的；数组可为空但不能省略键）：
  {
    "theme": "一句话主题",
    "concepts": [{"term": "术语", "definition": "一句话解释"}],
    "points": [{"time": "MM:SS 或 HH:MM:SS", "text": "带时间戳的要点"}],
    "evidence": [{"text": "论据或原文要点（精简）"}],
    "takeaways": ["可执行结论 / 行动项"]
  }
- 目标：帮助用户吸收来源——精简、好懂、可复查；禁止长散文堆砌。
- `points.time` 尽量来自字幕/时间轴，格式必须是 `MM:SS` 或 `HH:MM:SS`（前端要点时间戳可点击跳转播放）；没有可靠时间戳时可省略 time，只保留 text，禁止编造时间。
- `concepts` 只收关键术语；`takeaways` 要可执行，不要空话。
- 表单字段（`inputs.json` → `fields`）：
  - `focus`：可选聚焦问题（有则围绕它裁剪，无关内容不写）
  - `extra_constraints`：用户额外约束（若有，必须遵守）
- MANIFEST title：优先用 theme 精炼短标题。
