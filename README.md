# video-notebook

> Web 版 NotebookLM 克隆，视频专卖。系统内部使用，不公网暴露。

## 文档
- 需求：[`docs/requirements.md`](./docs/requirements.md)
- 设计：[`docs/superpowers/specs/2026-10-16-video-notebook-design.md`](./docs/superpowers/specs/2026-10-16-video-notebook-design.md)

## 仓库结构

```
.
├── docs/                         # 需求 + 设计
├── web/                          # Vite + React + shadcn/ui (本地进程)
├── api/                          # FastAPI (本地进程)
├── compose.middleware.yml        # 仅起 mysql + redis（开发期）
├── Makefile                      # 常用命令
└── .env.example                  # 环境变量模板
```

## 开发环境

### 前置
- Python 3.12+（用 uv 管理）
- Node 18+（用 npm 管理）
- Docker（仅用于跑 mysql + redis）
- 系统级：`ffmpeg`、`yt-dlp`（Phase 5 起需要）

### 启动

```bash
# 0. 准备 .env
cp .env.example .env

# 1. 启动中间件
make middleware

# 2. 启动 api（另一个终端）
make api
# → http://127.0.0.1:8000/docs

# 3. 启动 web（再一个终端）
make web
# → http://127.0.0.1:5173
```

### 健康检查
- API 直接健康：`curl http://127.0.0.1:8000/api/health` → `{"status":"ok"}`
- API + DB 探针：`curl http://127.0.0.1:8000/api/health/ready`
- Web 内置「健康检查」卡片（首页）每 5 秒刷一次

## 实施进度（按设计 §14 顺序）

| Phase | 内容 | 状态 |
|---|---|---|
| 1.1 | API 骨架 + 部署底座 | ✅ |
| 1.2 | Web 骨架 | ✅ |
| 1.3 | 中间件 compose + admin seed 落地 | ⏳（admin seed 随 Phase 2 User model 实装） |
| 2 | 鉴权与账号（User / JWT / admin users） | ⏳ |
| 3 | 模型配置（LLM / ASR + 加密层） | ⏳ |
| 4 | 笔记本 + 来源 + 上传 | ⏳ |
| 5 | URL 抓取 + 字幕链 | ⏳ |
| 6 | ASR 流水线 | ⏳ |
| 7 | 聊天 + SSE + 全上下文检索 | ⏳ |
| 8 | Skills 管理 | ⏳ |
| 9 | Agents 管理 + AgentRunner | ⏳ |
| 10 | Studio Mind Map | ⏳ |
| 11 | Studio PPT | ⏳ |
| 12 | Discover + Collections | ⏳ |
| 13 | 打磨 | ⏳ |
