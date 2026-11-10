- 主文件是阅读页 JSON，路径 `outputs/page.json`（UTF-8）。不要写 HTML、CSS 或 Markdown 页面。
- `outputs/MANIFEST.json` 必须是这一份，字段名不能改：
  {"status":"success","title":"短标题","artifacts":[{"role":"main","path":"outputs/page.json","mime":"application/json"}]}
- `title` 必须是短标题（≤20 字），优先用 fields.title，不要写整段 brief。
- 表单字段（`inputs.json` → `fields`）：
  - `title`：短标题
  - `brief`：已勾选要点、原句、时间、video_id、例子、评论和结论。只覆盖这些要点。
- JSON 形状（键名不能改；没有内容的可选字段省略，不要写空字符串或空数组）：

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
      "prose": "可选连贯段落；多段时改成字符串数组，最多 3 段",
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

- `sections` 至少 1 组，通常 2–6 组，不要超过 8 组。禁止一条要点一个 section，禁止把 20 条要点原样平铺。
- 一组里至少要有 `prose`、`steps`、`diagram`、`cards`、`callout` 之一。解释性的段落写 `prose`，不要为了凑数编成步骤。只有读者要照着做的短步骤才放 `steps`。
- 每个 step 必须有非空 `body`。`title` 是短步骤名，不要把整条要点塞进 title。
- `time` 只能是 `MM:SS` 或 `HH:MM:SS`，并且必须来自 brief 里该要点的「时间」行。每一步最多一个 time，取你引用的那条原句对应的时间。没有就省略 `time` 和 `video_id`。
- `video_id` 是整数，必须和该时间来自同一条要点。
- `quote` 只用 brief 里的「原句」短引。例子写进 `aside`，不要伪装成原句。「我的评论」可以写成 aside，不要写成出处。
- `theme` 必填，是论点而不是要点目录。`closing` 用结论收束，没有结论就省略。
- 图示仍只用 `diagram`，不要另起一套图的语法。`kind` 只能是 `flow`、`compare`、`sequence`。全文最多 3 个，同一种最多 2 个。材料不是流程、对照或节奏时就不要画。

图示怎么写（升级原有三种，不要再发明第四种 kind）：

- `flow`：横向流程。`nodes` 2–5 个，每项 `{label, detail}`。label 短，detail 一句。
- `compare`：两列表。`nodes` 里 `label` 是左格、`detail` 是右格。用 `columns` 写两个列名。错与对、旧与稳这种对照设 `"tone": "contrast"`；普通并列省略 tone。
- `sequence`：多条线的节奏图。`lanes` 是 2–4 个短列名（如角色或身体部位），`rows` 是 2–6 个节拍。每行 `{label, cells: [{lane, text}]}`，空着的列不要写 cell。`row_header` 可省略，默认当「节奏」。旧页面只写 `nodes` 仍然合法；新页面有明确的多列节奏时用 lanes + rows，不要两套都写。

其他块，只在材料本身适合时使用：

- `callout`：`{tone, label, body}`。`tone` 是 `note` 或 `warn`。`label` 最多 8 个字，如「要点」「注意」。全文最多 3 个。
- `cards`：属性卡，`[{title, body}]`，一组 2–6 张。全文最多 2 组。用来放并列的小属性，不要把步骤拆成卡片。

一页里不要把 flow、sequence、compare、cards、callout 全部用上。通常 1–3 个图示块就够。
