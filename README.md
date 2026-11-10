# 影知 · Videnote（video-notebook）

把视频变成可检索、可对话、可产出的**知识笔记本**（NotebookLM 风格，偏内部使用）。

品牌：**影知** / **Videnote**。同一套后端与笔记本数据，可从 **PC 网页**、**微信小程序**、**对外 Agent** 三条入口使用。

![笔记本列表](docs/images/home.png)

## 多端入口

| 端 | 适合做什么 | 说明文档 |
|----|------------|----------|
| **PC 网页**（`web/`） | 完整工作台：笔记本三栏、对话、知识底稿、导图/幻灯片、发现、管理后台 | [功能说明](docs/features.md) · [本地开发](docs/development.md) |
| **微信小程序**（`miniapp/`） | 手机收集入口：抖音等分享文案抽链 → 新建/加入笔记本 → 触发抓取 | [小程序说明](docs/miniapp.md) · [工程 README](miniapp/README.md) |
| **对外 Agent**（Skill + MCP） | WorkBuddy / Claude Code / Cursor 等：搜索视频、建本加片、读就绪状态、生成底稿 | [Agent 接入](docs/agent.md) · [功能说明 · Agent](docs/features.md#对外-agentworkbuddy--claude-code--cursor-等) |

- 小程序与外部 Agent 都走 **Agent API**（`Bearer vn_agent_…`），与网页 JWT 分离；笔记本数据互通。
- 小程序当前定位为**内网 / 体验版**方便入口，不必正式上架。
- Agent 默认**先搜索再停步**：入库、生成底稿需用户明确再说一次；未就绪来源时禁止生成底稿。

系统架构见 [架构](docs/architecture.md)。

## 核心能力

- **笔记本与来源** — URL / 上传入库，字幕与概览；网页搜索（B 站 / YouTube）加片；抖音等分享链接可经小程序或解析入库
- **标签** — Chip 筛选、管理标签、AI 自动整理
- **对话** — 勾选来源问答，引用回到字幕时间点
- **知识底稿** — 抽要点，一键生成思维导图 / 幻灯片（须全部来源字幕就绪）
- **发现** — 站内关键词与语义检索；笔记本可公开
- **管理后台** — 模型、抓取与网络、向量、账号、观测、**Agent 接入**（Token / Skill / MCP）

细节见 [功能说明](docs/features.md)、[需求](docs/requirements.md)。

## 快速开始（本地）

```bash
cp .env.example .env   # 改掉默认密码与密钥
make middleware        # MySQL / Redis / Qdrant（本机端口）
cd api && uv sync && cd ..
cd web && npm install && cd ..
make migrate
make api               # :8000
make web               # :5173
make media-worker      # 抓取 / 字幕 / 向量
make worker            # 导图 / PPT（需本机 Claude CLI）
```

- Web：http://127.0.0.1:5173  
- API：http://127.0.0.1:8000/docs  
- Agent 公开入口：`/agent/skill.md`、`/mcp`、`/llms.txt`、`/agent/install.sh`

首次登录用 `.env` 的 `SEED_ADMIN_*`。完整步骤与前置：[本地部署与开发](docs/development.md)。

小程序：`cd miniapp && npm install && npm run build:weapp`，用微信开发者工具打开 `miniapp`；在「我的」填可访问的 Server（勿用 localhost）与 Agent Token。

> 全栈 Docker Compose 部署稍后补充；当前以本地进程为主。

## 文档

| 文档 | 内容 |
|------|------|
| [功能说明](docs/features.md) | 现行能力（含网页、小程序、对外 Agent） |
| [微信小程序](docs/miniapp.md) | 抖音收集演示与页面一览 |
| [对外 Agent](docs/agent.md) | Token / Skill / MCP 接入节奏 |
| [架构](docs/architecture.md) | 组件与数据流 |
| [本地部署与开发](docs/development.md) | 中间件、进程、环境变量 |
| [需求](docs/requirements.md) | 产品范围与边界 |
| [miniapp 工程](miniapp/README.md) | Taro 编译与连接配置 |
