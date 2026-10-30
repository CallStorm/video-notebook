- 主文件是 JSON：`outputs/comic.json`。
- 结构（字段名不能改）：
  {
    "title": "短标题",
    "panels": [
      {"label": "误区", "caption": "...", "dialogue": "...", "scene": "..."},
      {"label": "冲突", "caption": "...", "dialogue": "...", "scene": "..."},
      {"label": "例子", "caption": "...", "dialogue": "...", "scene": "..."},
      {"label": "结论", "caption": "...", "dialogue": "...", "scene": "..."}
    ]
  }
- panels 必须恰好 4 格，label 顺序固定为 误区、冲突、例子、结论。
- `outputs/MANIFEST.json` 必须是这一份，字段名不能改：
  {"status":"success","title":"四格漫短标题","artifacts":[{"role":"main","path":"outputs/comic.json","mime":"application/json"}]}
- 表单字段（inputs.json → fields）：
  - title：短标题（可选）
  - brief：主题与要点材料（必填）
- MANIFEST.title 与 comic.json 的 title 用短主题名（≤24 字），不要贴整段 brief。
