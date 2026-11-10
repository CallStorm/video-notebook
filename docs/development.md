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

LLM / 语音转文字的 Key、抓取 Cookie、向量地址也可以在**后台配置**里改（向量默认常为 `http://127.0.0.1:6333`）。

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

## 目录约定

- `api/` — FastAPI + Celery workers
- `web/` — PC 网页
- `miniapp/` — 微信小程序
- `storage/` — 媒体与产物（gitignore）
- `skills/` — Studio 技能文件
