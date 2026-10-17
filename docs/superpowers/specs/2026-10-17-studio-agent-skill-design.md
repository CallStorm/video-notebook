# Studio · 能力、智能体与技能

> 2026-10-17 定稿。实现 Studio（思维导图、PPT、以及以后的产物格式）和它依赖的技能 / 智能体 / 能力配置。
>
> 本文取代 `docs/superpowers/specs/2026-10-16-video-notebook-design.md` 里关于 Studio、Agent、Skill 的章节（原文 §6.5、§7.3、§8、§10.3，以及 §14 的第 8–11 步）。那些章节里的 `agent.kind`、每种一个默认智能体、以及虚构的 `claude --skill-dir` 参数不再使用。
>
> 需求面仍以 `docs/requirements.md` 为准。本文对需求的唯一收窄：幻灯片不再单独做「建议长度」。篇幅写在能力表单的文本字段里，由用户或智能体提示决定。

## 1. 决定

笔记本右栏只显示已启用的 Studio 能力。一条能力选定一个智能体、一种产物格式，并自带一张可配置的表单。

三份配置彼此独立：

- **技能**：上传的目录，供智能体绑定。
- **智能体**：一次 Claude Code 运行的配置（skill、模型、系统提示、超时）。不分类，不设默认。
- **能力**：用户看见的入口（名称、图标、产物格式、智能体、表单、启用）。

产物格式写在代码里。它同时规定智能体必须交出什么文件、跑完怎么验收、以及用什么界面预览。现在登记三种：Markdown 导图、PPTX、文件。以后要新格式，只登记一种新的产物格式和它的预览。表单、智能体、技能都不用改。

同一次生成在任务上快照能力、智能体、产物格式和用户填写的字段。之后改配置，旧结果仍按快照打开。

## 2. 对象

### 2.1 技能

zip 上传，解压到 `skills_root/<id>/`。

- zip 根目录有 `SKILL.md`，直接作为技能根。
- 或者 zip 里只有一层文件夹，且该文件夹内有 `SKILL.md`，把这一层当作技能根。
- 除此之外拒绝。
- 成员路径含绝对路径、`..` 或以 `/` 开头的，整包拒绝，不落盘。
- 压缩包上限 32MB。

可改名称、说明、版本。可再打包下载。软删。有未删除的智能体引用它时不能删。

这期不预置任何技能。PPT 和导图用的包由管理员上传。

### 2.2 智能体

字段：名称、skill（可空）、模型名、系统提示、超时秒数。提供方固定为 `claude_code`，不出现在可选列表里。超时默认 600 秒，最小 30，最大 3600。

可启用、停用、软删。

- 停用后不能被选进能力。
- 停用时，凡 `agent_id` 指向它的能力，`enabled` 一并改为 false。
- 这些能力要重新启用，必须先换成一个启用中、且未删除的智能体。
- 仍被某条未删除能力的 `agent_id` 指着时，不能删。

### 2.3 能力

字段：名称、emoji 图标（最多 16 个字符，与笔记本图标同一存法）、产物格式、智能体、启用、表单字段、是否预置。

产物格式在创建时选定，之后不能改。名称、图标、智能体、启用和表单可以改。

表单字段是有序列表，只有三种：

| 类型 | 个数 | 配置 |
|---|---|---|
| `sources` | 最多 1 | 无额外项 |
| `language` | 最多 1 | 无额外项 |
| `text` | 多个 | `key`、标题、提示、是否必填、单行或多行 |

`key` 在一条能力内唯一，匹配 `^[a-z][a-z0-9_]{0,31}$`。

没有选中一个启用中的智能体时，不能启用。

预置两条，启动时若尚不存在则插入。已存在则不覆盖管理员改过的名称、图标、表单和智能体。

| 名称 | 图标 | 格式 | 表单 | 启用 |
|---|---|---|---|---|
| 思维导图 | 🧠 | `mind_map` | 语言、来源、必填单行文本「主题」（`key=topic`） | 否 |
| PPT | 📊 | `slides` | 语言、来源、必填多行文本「描述」（`key=brief`，提示写明受众、结构和期望页数） | 否 |

预置能力可以关，不能删。自建能力在没有任何任务时可以软删；有任务时只能关。

### 2.4 笔记勾选

左栏笔记补上与视频相同的勾选，字段 `notes.selected_for_chat`，默认 true。Studio 的来源默认值用视频和笔记各自的勾选。

普通聊天这期仍只发送视频 `source_ids`。笔记勾选只服务于 Studio 的来源字段，以及第 6.3 节的导图讨论。

## 3. 产物格式

代码登记表 `OutputFormat`：`key`、显示名、写进提示的输出要求、可接受的扩展名、预览种类。

管理员创建能力时，「产物格式」下拉只列出已登记项。一种格式对应一种预览，不能分开选。

### 3.1 `mind_map`

输出要求：

- 主文件是 markmap 用的 Markdown：`#` 为中心主题，子节点为缩进的无序列表。
- 路径 `outputs/mindmap.md`。
- `outputs/MANIFEST.json` 的 `title` 是导图名称，`artifacts` 有一项 `role=main`，`mime` 为 `text/markdown`。

扩展名：`.md`、`.markdown`。

### 3.2 `slides`

输出要求：

- 主文件是 pptx，路径 `outputs/deck.pptx`。
- 清单的 `mime` 为 `application/vnd.openxmlformats-officedocument.presentationml.presentation`。

扩展名：`.pptx`。

验收通过并写入对象存储后，worker 用 LibreOffice 转 PDF：

```
soffice --headless --convert-to pdf --outdir <work_dir>/outputs <pptx>
```

PDF 作为 `role=side` 的产物入库。转换失败时任务仍为成功，主文件保留，侧产物不入库，任务 `result_json.pdf_error` 记下短原因。

### 3.3 `file`

输出要求：一个非空主文件放在 `outputs/`，清单指向它并写上 `mime`。

扩展名不限制。没有清单时，`outputs/` 里必须恰好有一个非空文件。

### 3.4 清单

```json
{
  "version": 1,
  "status": "success",
  "title": "可选的显示名称",
  "artifacts": [
    { "role": "main", "path": "outputs/mindmap.md", "mime": "text/markdown" }
  ]
}
```

`path` 必须落在 `outputs/` 之内。验收只取 `role=main` 的第一项。`status` 不是 `success`、主文件缺失、空文件、或扩展名不在该格式的允许列表里，任务失败，错误码 `format_mismatch`。清单缺失或 JSON 无法解析时，改用该格式的兜底规则（第 5.4 节）；兜底也失败则为 `no_output`。

## 4. 数据模型

新表。时间字段沿用现有 `TimestampMixin`。软删用 `deleted_at`。

### `skills`

`id`，`name`（未删除范围内唯一），`description`，`version`，`storage_path`，`file_count`，`size_bytes`，`uploaded_by`，`deleted_at`。

### `agents`

`id`，`name`，`provider`（只允许 `claude_code`），`skill_id` 可空，`model_name`，`system_prompt`，`timeout_seconds`，`is_active`，`updated_by`，`deleted_at`。

### `studio_capabilities`

`id`，`name`，`icon`，`format_key`，`agent_id` 可空，`enabled`，`is_builtin`，`form_json`，`deleted_at`。

同一 `format_key` 的预置行最多一条（`is_builtin=true`）。自建能力可以复用同一格式。

### `studio_tasks`

`id`，`notebook_id`，`owner_id`，`capability_id`，`agent_id`，`format_key`，`title`，`status`，`params_json`，`error_code`，`error_message`，`result_json`，`started_at`，`finished_at`，`deleted_at`。

`status`：`queued` / `running` / `succeeded` / `failed` / `canceled`。

`error_code`：`timeout` / `process_failed` / `no_output` / `format_mismatch`，成功和取消时为空。

`params_json`：

```json
{
  "language": "中文",
  "video_ids": [1],
  "note_ids": [2],
  "fields": [{ "key": "topic", "label": "主题", "value": "…" }]
}
```

`title` 在排队和运行期间先用能力名称。成功后改写，顺序是：清单 `title`、用户填写的第一个文本字段、能力名称。取到的第一段非空文字即为标题，最长 255 字符。

### `studio_artifacts`

`id`，`task_id`，`role`（`main` 或 `side`），`filename`，`mime`，`storage_key` 可空，`text_content` 可空，`created_at`。

导图的主产物两份都写：`text_content` 存 Markdown，`storage_key` 存同一份文件。PPTX 和通用文件只写 `storage_key`。PDF 是 `side`，只写 `storage_key`。

### `notes` 加列

`selected_for_chat`，布尔，默认 true，非空。

## 5. 一次生成

### 5.1 API

`POST` 创建任务前检查：

- 调用者是笔记本所有者。
- 能力未删除且 `enabled`。
- 能力的智能体未删除且 `is_active`。
- 必填文本非空白。
- 表单含 `sources` 时，视频与笔记的选择合计至少一个，且都属于这本笔记本。
- 表单含 `language` 时，值只能是 `中文` 或 `English`。
- 表单没有的字段，请求里出现则拒绝。

通过后插入 `studio_tasks`，状态 `queued`，快照 `capability_id`、`agent_id`、`format_key` 和 `params_json`，提交事务，再投递 Celery 队列 `studio`。投递失败时把该任务标为 `failed` / `process_failed`，避免永远停在 `queued`。

API 进程不跑 Claude Code。字幕任务仍留在 API 进程里。

### 5.2 Worker

队列名 `studio`，并发 2。worker 镜像或宿主机需有 `claude` 和 `soffice`。

取到任务时，状态仍是 `queued` 才把状态改为 `running` 并写下 `started_at`。否则直接返回。

密钥读 worker 环境的 `ANTHROPIC_API_KEY`。模型名用智能体上的 `model_name`。聊天用的模型配置不传给这次运行。可选环境变量 `ANTHROPIC_BASE_URL` 原样交给进程。

工作目录 `<temp>/studio_<task_id>_<uuid>/`：

- `inputs.json`：`language`、`fields`、`sources`。每个来源有 `id`、`kind`（`video` 或 `note`）、`title`、`text`。视频 `text` 是整段字幕纯文本，笔记 `text` 是全文。不截断。
- `.claude/skills/<技能目录名>/`：智能体绑了 skill 时，把 `storage_path` 整份复制进来。目录名用技能的 `name` 转成文件系统安全的一段。没绑 skill 则不建这个目录。
- `outputs/`：空目录。
- `prompt.txt`：第 5.3 节的提示。

技能目录已经不在磁盘上时，不启动进程，任务 `failed` / `process_failed`。

### 5.3 提示

三截按这个顺序写进 `prompt.txt`：

1. 该产物格式的输出要求。
2. 智能体的系统提示。为空则这一截只有标题。
3. 固定说明：阅读 `inputs.json`；若工作目录里有 skill，点名使用它；不要改 `inputs.json`；主文件和 `outputs/MANIFEST.json` 都写在 `outputs/` 下。

进程：

```
claude -p --permission-mode bypassPermissions --model <model_name> --add-dir <work_dir>
```

工作目录是 `work_dir`。`prompt.txt` 的正文从标准输入送入。stdout / stderr 落在工作目录的 `stdout.log` 和 `stderr.log`。

超时用智能体的 `timeout_seconds`。到点向进程组发 `SIGTERM`，5 秒后仍在则 `SIGKILL`。任务 `failed` / `timeout`。

### 5.4 验收与入库

进程退出码不是 0：`failed` / `process_failed`。`error_message` 保留 stderr 末尾 2000 字符，供排查。界面只显示第 8 节的四类中文，不展示这段日志。

退出码是 0 时：

1. 读 `outputs/MANIFEST.json`。清单可用则按第 3.4 节验收。
2. 清单缺失或损坏时：在 `outputs/` 直接下级找非空文件。`mind_map` 和 `slides` 只认自己的扩展名，且必须恰好一个。`file` 必须恰好一个非空文件。命中则当作主产物。零个或多个都是 `no_output`。

主产物复制进现有对象存储。导图同时把文本写入 `text_content`。幻灯片再转 PDF（第 3.2 节）。然后把任务标为 `succeeded`，按第 4 节改写 `title`。

成功后删除工作目录。失败则保留 24 小时。worker 启动时，以及之后每 10 分钟，做两件事：把 `running` 且 `started_at` 早于「该任务智能体超时 + 60 秒」的任务标为 `failed` / `process_failed`；删掉失败时间已超过 24 小时的工作目录。正常超时已经在第 5.3 节处理，扫描只收拾 worker 自身中断留下的任务。

### 5.5 取消

所有者 `DELETE` 一条未软删的任务时，写上 `deleted_at`，列表不再返回。API 不向 Claude 进程发信号，因为进程在 worker 里。

- 当时是 `queued`：状态改为 `canceled`。worker 开工前看到不是 `queued`，直接返回。
- 当时是 `running`：状态改为 `canceled`。正在跑的 worker 每 2 秒读一次这条任务，看到 `canceled` 或 `deleted_at` 就结束自己的进程组。它在写入 `succeeded` 之前再读一次；若已取消，则不改成成功，并删掉已经拷进对象存储的文件。
- 当时已是 `succeeded`、`failed` 或 `canceled`：删掉对象存储上的产物。

关掉能力不打断已经 `queued` 或 `running` 的任务，只拒绝新建。

## 6. 笔记本里的 Studio

### 6.1 右栏

上方是已启用能力，用配置的 emoji 和名称。下方是本笔记本的任务，新的在前。

- 进行中：显示能力名称，可删除。
- 失败：显示第 8 节的四类原因之一，可删除。
- 成功：显示标题。点击进入预览。

预览占右栏。顶栏可以回到 Studio。右上角可以铺满整个笔记本页面（不换路由）。更多菜单里可以删除。

### 6.2 创建表单

完全由能力的 `form_json` 生成。

- 语言：下拉，只有「中文」和「English」。
- 来源：列出这本笔记本的视频和笔记。视频默认取 `selected_for_chat=true` 的，笔记同样。用户可以在弹层里改这次的选择，不写回左栏勾选。
- 文本：按配置显示单行或多行，必填的不能空白提交。

提交后右栏立刻出现一条进行中的记录，标题先用能力名称。

### 6.3 Markdown 导图

用 `markmap-lib` 把 `text_content` 转成树，用 `markmap-view` 画。不另存一份 JSON 树。

左侧：放大、缩小、全部展开、下载 Markdown（即 `text_content`）。左上角列出这次快照里的来源标题。点视频在左栏打开该视频；点笔记在右栏打开该笔记的只读内容，导图预览让位，从笔记返回时回到这张导图。

点折叠控件只展开或收起。点节点文字时导图保持打开，中栏送出一条用户消息：

- 有父节点：`Discuss what these sources say about {当前节点文字}, in the larger context of {父节点文字}.`
- 根节点：`Discuss what these sources say about {当前节点文字}.`

节点文字去掉 Markdown 标记后填入。这条消息走现有聊天接口。上下文不用左栏当前勾选，而用任务快照：视频 `source_ids` 取 `params_json.video_ids`；这些笔记的全文追加在字幕上下文之后，不参与引用编号。聊天失败只显示在中栏，导图和任务状态不变。

### 6.4 PPTX

右栏用 iframe 打开 PDF 产物的签名地址，页内滚动。铺满时同一个 iframe。更多菜单下载原始 PPTX 和 PDF。

`pdf_error` 有值时，右栏说明预览不可用，PPTX 下载仍在，PDF 下载不出现。

### 6.5 文件

记录上提供主文件下载。没有画布，没有铺满，没有节点点击。

### 6.6 非所有者

本轮不新做发现页。接口规则先定下：只有所有者可以创建和删除。非所有者一律 404，分享实装后再对「能读这本笔记本的人」开放 GET 和下载。

## 7. 后台

三页，都要求管理员。普通用户 403。

- `/admin/skills`
- `/admin/agents`
- `/admin/studio`

改配置只影响之后新建的任务。

技能页：列表含名称、版本、大小、上传时间。上传、改元数据、下载、删除。删除被引用时返回 409。

智能体页：列表含名称、技能名、模型、超时、启用。新建和编辑用第 2.2 节的字段。停用走第 2.2 节的连动。

能力页：列表含图标、名称、产物格式、智能体名称、启用开关。新增用第 2.3 节的字段。产物格式创建后不可改，`PATCH` 若带 `format_key` 则 400。智能体下拉只列启用中的。`form_json` 数组顺序就是表单顺序。启用时若智能体未启用或已删除，返回 409，开关保持关闭。

## 8. 用户可见的失败

界面只显示这四句，对应 `error_code`：

| 码 | 界面 |
|---|---|
| `timeout` | 超时 |
| `process_failed` | 进程失败 |
| `no_output` | 没有主产物 |
| `format_mismatch` | 格式不对 |

创建请求的拒绝用现有错误体，不进任务表：能力未启用、智能体未启用、必填为空、来源不属于该笔记本、来源一个都没选、语言不在两档之内。

## 9. API

管理员：

```
GET    /api/admin/skills
POST   /api/admin/skills                  multipart file
GET    /api/admin/skills/{id}
PATCH  /api/admin/skills/{id}             name, description, version
GET    /api/admin/skills/{id}/download
DELETE /api/admin/skills/{id}

GET    /api/admin/agents
POST   /api/admin/agents
GET    /api/admin/agents/{id}
PATCH  /api/admin/agents/{id}
POST   /api/admin/agents/{id}/disable
POST   /api/admin/agents/{id}/enable
DELETE /api/admin/agents/{id}

GET    /api/admin/studio/formats
GET    /api/admin/studio/capabilities
POST   /api/admin/studio/capabilities
GET    /api/admin/studio/capabilities/{id}
PATCH  /api/admin/studio/capabilities/{id}
POST   /api/admin/studio/capabilities/{id}/disable
POST   /api/admin/studio/capabilities/{id}/enable
DELETE /api/admin/studio/capabilities/{id}
```

笔记本：

```
GET    /api/notebooks/{id}/studio/capabilities
GET    /api/notebooks/{id}/studio/tasks
POST   /api/notebooks/{id}/studio/tasks
GET    /api/studio/tasks/{id}
DELETE /api/studio/tasks/{id}
GET    /api/studio/tasks/{id}/artifacts/{artifact_id}
```

`POST .../tasks` 的正文是 `capability_id`、可选 `language`、`video_ids`、`note_ids`、`fields`（`key` → 字符串）。

任务列表不带产物正文。`GET /api/studio/tasks/{id}` 在导图成功时带上主产物的 `text_content`，供 markmap 直接画。文件类产物的 `GET .../artifacts/{id}` 与现有播放地址一样，返回 `{url, expires_in}`，`url` 是存储代理的签名地址。PDF 预览和 PPTX、PDF、通用文件的下载都走这个 JSON，不用浏览器直读磁盘路径。

讨论不新增端点。`POST /api/notebooks/{id}/chat` 增加可选字段 `note_ids`。导图节点点击时，前端传入快照里的 `video_ids` 作为 `source_ids`，传入快照里的 `note_ids`。服务端用这些 id 组装上下文，不读左栏当前勾选。笔记全文接在字幕之后，不参与引用编号。不传 `note_ids` 时，普通聊天与现在一致。

## 10. 代码位置

- `api/app/models/studio.py`：五张表对应的模型；笔记列改在现有 `Note` 上。
- `api/app/studio/formats.py`：三种格式的登记、提示段落、验收。
- `api/app/studio/runner.py`：工作目录、提示、进程、入库。
- `api/app/studio/worker.py`：Celery 应用与 `studio.run` 任务。开发期单独进程启动，不进 `make api`。
- `api/app/services/skills.py`、`agents.py`、`capabilities.py`
- `api/app/routes/admin_skills.py`、`admin_agents.py`、`admin_studio.py`、`studio.py`
- `web/src/pages/admin-skills.tsx`、`admin-agents.tsx`、`admin-studio.tsx`
- `web/src/pages/notebook.tsx` 的右栏接上能力列表、任务列表和预览。导图和幻灯片预览拆成独立组件。

种子放在应用启动路径里，条件与第 2.3 节相同。不放进管理员账号的种子函数。

## 11. 测试

不调用真的 Claude Code，也不要求测试机安装 LibreOffice。PDF 转换在单测里用一个可替换的函数替身。

- 清单正确、清单缺失但恰好一个合法文件、扩展名不对、空文件、多个文件。
- 来源和语言各自不能有两个；没有合格智能体不能启用能力；被引用的技能删除返回 409；预置能力删除返回 409；有任务的自建能力删除返回 409。
- 假的 `claude` 可执行文件写出 Markdown 和清单后，任务成功，`text_content` 能读回。
- 排队中的任务删除后，worker 不再把它跑成成功。
- 超时、退出码非 0、格式不对，三条各自落到对应的 `error_code`。
- 非所有者创建任务得到 404。
- 不传 `note_ids` 的聊天请求，上下文与现在一致。

## 12. 实施顺序

一份计划，按这个顺序写，前一步的测试通过再进下一步：

1. 表、技能、智能体、能力、三种格式登记、预置两条能力、笔记勾选。
2. 创建任务、Celery worker、运行器、验收、取消。
3. 后台三页。
4. 笔记本右栏：表单、任务列表、三种预览、导图节点讨论。

## 13. 这期不做

- 第四种产物格式，以及任意新控件。
- 按种类设默认智能体，或每个用户一套智能体。
- 单独的建议长度步骤。
- 失败后自动重试。
- 把字幕任务迁到 Celery。
- 发现页本身。只预留第 6.6 节的接口规则。
- 把智能体的额外参数拼进 `claude` 命令行。
