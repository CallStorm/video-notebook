---
name: knowledge-draft
description: 把笔记本来源整理成知识底稿 JSON（主题、概念、带时间戳的要点和短例子）。一条来源精读，多条来源对比。
---

# 知识底稿

阅读 `inputs.json`，写出 `outputs/draft.json` 和 `outputs/MANIFEST.json`。

## 写法

- 一条来源：精读。主题一句，概念 3–8 个，要点 5–12 条，按时间排。
- 两条及以上：对比。相同点和不同点分开，要点带 `source_hint`。
- `focus` 有内容时，只留和它直接相关的要点。
- 有可靠的 `[分:秒]` 才写 `time`。`evidence` 是原句短引。`example` 是生活短例子，不抄字幕。
- 不写结论，不铺字幕。

## draft.json

```json
{
  "theme": "一句话主题",
  "concepts": [{"term": "术语", "definition": "一句话解释"}],
  "points": [
    {
      "text": "要点",
      "time": "MM:SS",
      "evidence": "原句短引",
      "example": "生活短例子",
      "example_kind": "life",
      "source_hint": "video:12",
      "video_id": 12
    }
  ],
  "takeaways": [],
  "open_questions": []
}
```

`time`、`evidence`、`source_hint`、`video_id` 没有把握就省略。`example` 不能空。
