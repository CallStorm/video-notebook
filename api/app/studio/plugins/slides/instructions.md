- 主文件是 pptx，路径 `outputs/deck.pptx`。
- `outputs/MANIFEST.json` 必须是这一份，字段名不能改，也不要写成技能自己的清单：
  {"status":"success","title":"短主题名","artifacts":[{"role":"main","path":"outputs/deck.pptx","mime":"application/vnd.openxmlformats-officedocument.presentationml.presentation"}]}
- `title` 必须是短主题名（≤20 字），不要写整段 brief 或「受众/结构建议/页数」行。
- 提交前确认 deck 里至少有一页真实幻灯片（`officecli view deck.pptx outline` 能看到页数）；只 create 不 add slide 的空壳会被拒绝。
- 页上禁止粘贴 brief 元数据块（受众、结构建议、页数、主题标签、原句摘要）；封面短标题，内容页短标题 + ≤3–5 条短要点并留白。
