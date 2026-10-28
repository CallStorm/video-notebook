- 主文件是 pptx，路径 `outputs/deck.pptx`。
- `outputs/MANIFEST.json` 必须是这一份，字段名不能改，也不要写成技能自己的清单：
  {"status":"success","title":"演示标题","artifacts":[{"role":"main","path":"outputs/deck.pptx","mime":"application/vnd.openxmlformats-officedocument.presentationml.presentation"}]}
- 提交前确认 deck 里至少有一页真实幻灯片（`officecli view deck.pptx outline` 能看到页数）；只 create 不 add slide 的空壳会被拒绝。
