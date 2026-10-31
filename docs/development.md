# 本地部署与开发

当前推荐路径：**本机跑 api / web / worker**，仅用 Docker 起中间件（MySQL、Redis、Qdrant）。全栈 Docker Compose 暂未作为主路径（稍后补充）。

## 前置

- Python 3.12+（建议 [uv](https://github.com/astral-sh/uv)）
- Node 18+（npm）
- Docker（仅用于中间件容器）
- 系统：`ffmpeg`；YouTube 抓取建议安装 Deno（EJS challenge）
- 导图 / PPT：本机可用的 Claude CLI（studio-worker）

## 一键起本地

```bash
cp .env.example .env   # 已有勿覆盖；改掉 JWT / MYSQL / SEED 密码
make middleware        # mysql:3306 redis:6379 qdrant:6333（绑 127.0.0.1）
cd api && uv sync && cd ..
cd web && npm install && cd ..
make migrate           # alembic upgrade head
make api               # http://127.0.0.1:8000/docs
make web               # http://127.0.0.1:5173  （/api → 8000）
make media-worker      # 抓取 / 字幕 / 向量
make worker            # 导图 / PPT
```

首次登录用 `.env` 里的 `SEED_ADMIN_PHONE` / `SEED_ADMIN_PASSWORD`（无 admin 时 seed）。

健康检查：

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/health/ready
```

停中间件：`make down`（默认保留数据卷）。

## 环境变量（本地）

见根目录 `.env.example`。本地要点：

| 变量 | 本地典型值 |
|------|------------|
| `MYSQL_HOST` | `127.0.0.1` |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` |
| `STORAGE_ROOT` / `SKILLS_ROOT` | `./storage` / `./skills` |
| `SEED_ADMIN_*` | 首个管理员 |

LLM / ASR Key、抓取 Cookie、向量地址也可在**管理后台**配置（向量默认常为 `http://127.0.0.1:6333`）。

Celery：`CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` 若未单独配置，一般跟 Redis 约定（见 api 配置）。

## 常用 make

| 命令 | 作用 |
|------|------|
| `make middleware` / `make down` | 起 / 停中间件 |
| `make api` / `web` / `media-worker` / `worker` | 本机进程 |
| `make migrate` | 升库 |
| `make test` / `typecheck` / `build` | 测试与构建 |

`make help` 看完整列表。

## 目录约定

- `api/` — FastAPI + Celery workers
- `web/` — 前端
- `storage/` — 媒体与产物（gitignore）
- `skills/` — Studio 技能文件
