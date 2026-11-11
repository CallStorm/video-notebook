---
name: reading-page
description: 把已勾选的知识要点重组成阅读页 JSON（论点、分组、步骤卡、流程/对照/节奏图、属性卡和提示）。不要输出 HTML。
---

# 阅读页

阅读 `inputs.json`，写出 `outputs/page.json` 和 `outputs/MANIFEST.json`。

页面由产品渲染。你只提供结构化内容，不要写 HTML、CSS 或 Markdown 页面。

## 怎么重组

把 brief 里的要点当成素材，而不是目录。

- 先用一句话写出全文论点，放进 `theme`。
- 再按主题分成 2–6 组。相关要点合并。解释性的话写进 `prose`，要照着做的短步骤才写 `steps`。
- 要点很多时也保持这个组数。不要出现和要点条数一样多的 section。
- 每一步写成读者能顺着读下去的 1–3 句，而不是「要点：……」的复读。
- 图示只用 `diagram`，kind 仍是 `flow`、`compare`、`sequence`。全文最多 3 个，同一种最多 2 个。
- `callout` 全文最多 3 个。`cards` 最多 2 组，每组 2–6 张。不要为了好看把每种块都放上去。

## 三种图

- 流程：`kind: flow`，`nodes` 为 `{label, detail}`。
- 对照表：`kind: compare`，`columns` 两个列名，`nodes` 的 label / detail 是左右两格。错对对照加 `"tone": "contrast"`。
- 节奏图：`kind: sequence`，`lanes` 2–4 个列名，`rows` 里每行 `{label, cells: [{lane, text}]}`。没有多列节奏时，可以只写原来的 `nodes`。

## 时间与原句

- `time` / `video_id` 只能从要点行原样抄。没有「时间」就不要写这两个字段。
- 一步只保留一个时间，对应该步引用的那句原话。
- `quote` 是原句短引。例子和「我的评论」放 `aside`。

## 不要写进页面

受众、结构建议、页数、主题标签、要点编号。这些只用于规划。
