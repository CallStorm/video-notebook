# 功能说明

按**当前实现**介绍。产品边界见 [requirements.md](requirements.md)。

同一后端支撑三端：**PC 网页**（下文前半）、**微信小程序**（[miniapp.md](miniapp.md)）、**对外 Agent**（下文专节与 [agent.md](agent.md)）。总览见根 [README](../README.md)。

## 笔记本与来源

- **笔记本**：创建 / 列表 / 置顶 / 公开 / 删除；封面；打开后三栏（来源 · 对话 · 知识/产物）。
- **来源**：本地上传；粘贴 URL（YouTube / 直链等，yt-dlp）；笔记本内**网页搜索**（B 站 / YouTube）加入。
- **字幕**：内嵌 → 平台字幕 → ASR；可重试。
- **概览**：默认 LLM 生成。

![笔记本三栏：来源 · 对话 · 知识](images/notebook.png)

*笔记本内：左栏来源、中栏对话、右栏知识/产物。*

![网页搜索加片](images/web-search.png)

*网页搜索：按关键词搜 B 站 / YouTube，点「加入」入库。*

Cookie / 代理在 **后台 → 抓取与网络** 按平台配置。

## 标签

- 多对多挂在笔记本；首页 Chip 筛选（不展示关联数为 0 的标签）。
- **管理标签**：手建 / 改名 / 删。
- **自动整理**：据名称与描述生成方案，确认后覆盖关联；不落库空标签。

![首页标签 Chip 与笔记本列表](images/home.png)

*首页：标签筛选、自动整理、笔记本卡片。*

![管理标签](images/manage-tags.png)

*管理标签：创建、配色、删除。*

## 对话

- 只用左栏**勾选**来源作上下文；可配历史轮数。
- 回答可带引用，能回到字幕时间点；可存笔记。

（对话区见上图笔记本三栏中栏。）

## 知识底稿与产物

- **知识底稿**：字幕就绪后按策略抽要点（后台可配策略与 `max_tokens`）。
- **思维导图 / 幻灯片**：勾选要点后入队，由 studio-worker 生成（需 Claude CLI）。

![知识底稿要点](images/knowledge-draft.png)

*知识底稿：概念标签、可勾选要点，可生成导图 / 幻灯片。*

## 发现

- 站内范围：全部 / 我的 / 公开。
- 关键词与语义检索（Qdrant）。

![发现页](images/discover.png)

*发现：检索公开/我的笔记本。*

## 账号与后台

- 账号由管理员创建；手机号 + 密码；角色：用户 / 管理员。
- 后台：模型（LLM/ASR）、抓取与网络、向量、底稿策略、账号、运行观测（流水线 / LLM traces）等。
- 健康检查：`GET /api/health`、`GET /api/health/ready`。

## 微信小程序

手机端收集入口（抖音分享文案抽链 → 新建/加入笔记本 → 自动抓取）。演示与截图见 [miniapp.md](miniapp.md)；工程说明见 [miniapp/README.md](../miniapp/README.md)。

## 对外 Agent（WorkBuddy / Claude Code / Cursor 等）

把影知接到外部编程 Agent：用 **Agent Token + Skill + MCP**，不要把整站 `/api` 登录 JWT 交给 Agent。入口在网页 **后台配置 → Agent 接入**。

### 能力概览

| 能力 | 说明 |
|------|------|
| 搜索视频 | `search`：YouTube / Bilibili（当前不支持抖音） |
| 笔记本 | `create_notebook` / `list_notebooks` / `get_notebook` / `delete_notebook` |
| 加片入库 | `add_url` 后异步抓取；`get_readiness` 看字幕是否就绪 |
| 知识底稿 | 全部来源字幕就绪且用户明确要求后，才 `generate_draft`；未就绪会硬拒绝 |
| 读取产物 | `get_draft` 读知识正文；`list_artifacts` / `get_artifact`；`download_video` 签名 URL |
| 标签 | `list_tags`；可配合自动归类相关工具 |

**默认停步**：未获用户明确指令时，禁止把「搜索 → 入库 → 生成底稿」串成一条自动流水线。只搜就只汇总结果并停下；建本、加链接、生成底稿都要用户再说一次。

### 接入步骤（图示）

1. **创建 Token 并拿到安装命令**  
   在 Agent 接入页创建 Token（明文只显示一次，可撤销）。把安装命令发给正在使用的客户端（WorkBuddy / Claude Code / Cursor 等）；由**该客户端里的 Agent**按本客户端规范自装 Skill 与 MCP，不要假定只写 `~/.cursor/mcp.json`。

![Agent 接入：创建 Token 与安装说明](images/agent-01-access.png)

*图 1 · 后台「Agent 接入」：创建 Token，下发安装命令；可查看 `llms.txt` / `skill.md` / MCP。*

2. **安装完成后开始提问（先搜索）**  
   Skill / MCP 就绪后，用自然语言让 Agent 搜片。Agent 应只调用搜索、整理结果，等你指定要入库的链接。

![WorkBuddy 中搜索抬头蛙相关视频](images/agent-02-search.png)

*图 2 · WorkBuddy：按主题搜索并分类列出结果；备注可标出已在某笔记本中的片。*

3. **明确要求后创建笔记本**  
   例如：「创建一个抬头蛙笔记本，把下面这两条加入」。Agent 再 `create_notebook` + `add_url`。

![我的笔记本中出现新建本](images/agent-03-notebook.png)

*图 3 · 网页「我的笔记本」：Agent 创建的笔记本已出现（封面可能仍在生成）。*

4. **自动开始抓取链接**  
   加入的 URL 进入抓取与字幕流水线；网页来源栏可看到「字幕就绪」等状态。

![笔记本内来源抓取与字幕就绪](images/agent-04-fetch.png)

*图 4 · 笔记本详情：来源已加入并抓取；字幕就绪后才能生成底稿。*

5. **就绪后再在客户端要求生成底稿**  
   当 `ready_for_draft = true`（本内全部来源字幕就绪），在 WorkBuddy 等客户端说「生成知识底稿」。Agent 会创建与网页相同的底稿任务；可用 `get_job` 轮询，成功后 `get_draft` 读正文。

![WorkBuddy 汇报入库完成并询问是否生成底稿](images/agent-05-draft-ready.png)

*图 5 · 客户端汇报：抓取 2/2 就绪后按规则停步，询问是否生成知识底稿。*

### 认证与边界

- Token：`Authorization: Bearer vn_agent_…`；登录用 JWT 会被拒绝。
- 权限大致分：`read`（搜与读）、`write_notebook`（建本/加链）、`write_generate`（封面/底稿）。
- 媒体只通过签名 URL 下载，工具结果不含视频/图片二进制。
- 公开入口：`/agent/skill.md`、`/mcp`、`/agent/v1/tools/<name>`、`/llms.txt`、`/agent/install.sh`。
