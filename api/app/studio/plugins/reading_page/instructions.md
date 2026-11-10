- 主文件是阅读页 JSON，路径 `outputs/page.json`（UTF-8）。不要写 HTML。
- `outputs/MANIFEST.json` 必须是这一份，字段名不能改：
  {"status":"success","title":"短标题","artifacts":[{"role":"main","path":"outputs/page.json","mime":"application/json"}]}
- `title` 必须是短标题（≤20 字），优先用 fields.title，不要写整段 brief。
- 表单字段（`inputs.json` → `fields`）：
  - `title`：短标题
  - `brief`：已勾选要点、原句、时间、video_id、例子、评论和结论。只覆盖这些要点。
- JSON 形状（键名不能改；没有内容的可选字段省略，不要写空字符串）：

```json
{
  "title": "短标题",
  "kicker": "可选一行眉题",
  "theme": "全文论点，1–2 句，放在开篇",
  "lede": "把材料收成一段导语",
  "sections": [
    {
      "id": "s1",
      "title": "这一组的主题",
      "summary": "这一组要解决什么",
      "steps": [
        {
          "title": "步骤名",
          "body": "1–3 句连贯说明，可合并多条相关要点",
          "time": "MM:SS",
          "video_id": 12,
          "quote": "原句短引",
          "aside": "例子或读者评论，可选"
        }
      ],
      "diagram": {
        "kind": "flow",
        "caption": "可选说明",
        "nodes": [{"label": "节点", "detail": "可选"}]
      }
    }
  ],
  "closing": "把结论收成一段话"
}
```

- `sections` 至少 1 组，通常 2–6 组。禁止一条要点一个 section，禁止把 20 条要点原样平铺。
- 每个 step 必须有非空 `body`。`title` 是短步骤名，不要把整条要点塞进 title。
- `time` 只能是 `MM:SS` 或 `HH:MM:SS`，并且必须来自 brief 里该要点的「时间」行。每一步最多一个 time，取你引用的那条原句对应的时间。没有就省略 `time` 和 `video_id`。
- `video_id` 是整数，必须和该时间来自同一条要点。
- `quote` 只用 brief 里的「原句」短引。例子写进 `aside`，不要伪装成原句。「我的评论」可以写成 aside，不要写成出处。
- `diagram` 只在流程、对比或因果说得清时使用。`kind` 只能是 `flow`、`compare`、`sequence`。全文最多 2 个。节点 2–5 个，label 要短。
- `theme` 必填，是论点而不是要点目录。`closing` 用结论收束，没有结论就省略。
