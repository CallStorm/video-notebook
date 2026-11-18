# 本地部署与开发

当前推荐：**本机跑 api / web / worker**，只用 Docker 起中间件（MySQL、Redis、Qdrant）。`make up` 可以构建全栈 Compose，但还不是主路径。

采集三条平台的差异见 [采集说明](collection.md)。产品能力见 [功能说明](features.md)。

## 前置

- Python 3.12+（建议 [uv](https://github.com/astral-sh/uv)）
- Node 18+（npm）
- Docker（仅用于中间件容器）
- 系统：`ffmpeg`；YouTube 抓取建议安装 Deno（没有则尝试 Node）
- 导图、幻灯片、阅读页：本机可用的 Claude CLI（studio-worker）

## 快速开始（本地）

```bash
cp .env.example .env   # 已有 .env 不要覆盖；改掉 JWT、数据库和管理员密码
make middleware        # MySQL :3306、Redis :6379、Qdrant :6333（绑 127.0.0.1）
cd api && uv sync && cd ..
cd web && npm install && cd ..
make migrate           # alembic upgrade head
make api               # http://127.0.0.1:8000
make web               # http://127.0.0.1:5173  （/api → 8000）
make media-worker      # 抓取 / 字幕 / 向量
make worker            # 导图 / 幻灯片 / 阅读页
```

- Web：http://127.0.0.1:5173
- API 文档：http://127.0.0.1:8000/docs
- Agent 公开入口：`/agent/skill.md`、`/mcp`、`/llms.txt`、`/agent/install.sh`

首次登录用 `.env` 里的 `SEED_ADMIN_PHONE` / `SEED_ADMIN_PASSWORD`（库里还没有管理员时会写入）。

健康检查：

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/health/ready
```

停中间件：`make down`（默认保留数据卷）。

微信小程序不在上面这组进程里，见下一节。

## 微信小程序

```bash
cd miniapp
npm install
npm run build:weapp
```

用微信开发者工具打开 `miniapp`（`project.config.json` 的 `miniprogramRoot` 指向 `dist/`）。开发期关闭合法域名校验。

在小程序「我的」填写：

- Server URL：手机或模拟器能访问的后端，例如 `http://192.168.x.x:8000`（不要用 `localhost`）
- Agent Token：网页 **设置 → Agent 接入** 创建的 `vn_agent_…`

AppID `wx807def5a62c2af59` 用于内网、开发或体验入口，不必正式上架。开发者工具命令行等细节见 [miniapp/README.md](../miniapp/README.md)。

## 环境变量（本地）

见根目录 `.env.example`。本地要点：

| 变量 | 本地典型值 |
|------|------------|
| `MYSQL_HOST` | `127.0.0.1` |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` |
| `STORAGE_ROOT` / `SKILLS_ROOT` | `./storage` / `./skills` |
| `SEED_ADMIN_*` | 首个管理员 |

LLM / 语音转文字的 Key、抓取 Cookie、向量地址也可以在**后台配置**里改（向量默认常为 `http://127.0.0.1:6333`）。本地对话模型见下文 [本地 LLM](#local-llm)。 自建 ASR 的配置见[语音转文字](asr.md)。

Celery 的 `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` 若未单独配置，一般跟 Redis 约定（见 api 配置）。

## 常用 make

| 命令 | 作用 |
|------|------|
| `make middleware` / `make down` | 起 / 停中间件 |
| `make api` / `web` / `media-worker` / `worker` | 本机进程 |
| `make migrate` | 升库 |
| `make test` / `typecheck` / `build` | 测试与构建 |
| `make up` / `make down-all` | 全栈 Compose 起 / 停（不是当前主路径） |

`make help` 看完整列表。

<a id="local-llm"></a>

## 本地 LLM

对话、来源概览、笔记辅助、知识底稿（生成、修复、要点追问、结论核对）、底稿策略试跑、标签整理，以及未单独指定时的图标，都走当前的**聊天模型**。MiniMax 仍走 Anthropic 兼容接口。OpenAI、DeepSeek 和本机服务走 OpenAI Chat Completions（`/v1/chat/completions`）。

可以接 Ollama、LM Studio、vLLM、llama.cpp server，或任何提供该接口的进程。封面文生图、向量模型和语音转文字仍用各自的默认项，不会跟着聊天模型改。

### 后台

1. 打开后台的模型配置，为 Ollama 选择 **Ollama**，为 LM Studio、vLLM 或 llama.cpp 选择 **本地 OpenAI 兼容**，添加凭证。
2. Base URL 可填完整 API 前缀。只填主机和端口时自动补 `/v1`。API Key 可留空；服务要求鉴权时再填。
3. 「发现模型」或手动填写模型名（例如 `qwen2.5`），类型为对话。
4. 把该模型设为 **聊天模型**。如需向量检索，可用同一凭证注册单独的 embedding 模型，并设为**向量模型**。

| 服务 | Base URL 示例 |
|------|----------------|
| Ollama | `http://127.0.0.1:11434/v1` |
| LM Studio | `http://127.0.0.1:1234/v1` |
| vLLM | `http://127.0.0.1:8001/v1`（本机 API 已占用 8000） |
| llama.cpp server | `http://127.0.0.1:8080/v1` |

API 或 worker 运行在容器中时，回环地址指向容器自身。模型运行在另一台机器时，填写 API 和 worker 都能访问的私网地址，例如 `http://<模型主机>:11434/v1`。Studio 的 Claude Code 引擎有独立配置。

Ollama 示例：

```bash
ollama serve
ollama pull qwen2.5
# 凭证 Base URL: http://127.0.0.1:11434/v1
# 模型名: qwen2.5
```

本地上下文通常比云端模型短。底稿默认 `max_tokens` 很大，服务拒绝时把环境变量 `DRAFT_MAX_TOKENS` 或后台「底稿策略」里的上限调低。

### 环境变量

库里还没有默认聊天模型时，才读取下面四项。后台已经指定聊天模型时，以后台为准。

```bash
LLM_PROVIDER=ollama
LLM_BASE_URL=http://127.0.0.1:11434/v1
LLM_MODEL_NAME=qwen2.5
LLM_API_KEY=
```

`LLM_PROVIDER` 也可以是 `openai` 或 `deepseek`，这时需要 `LLM_API_KEY`。未填模型名时不会偷偷启用。

## 目录约定

- `api/` — FastAPI + Celery workers
- `web/` — PC 网页
- `miniapp/` — 微信小程序
- `storage/` — 媒体与产物（gitignore）
- `skills/` — Studio 技能文件
