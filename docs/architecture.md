# 架构

以当前仓库代码为准。

## 总览

本地开发时：浏览器打 Vite（`:5173`），`/api` 代理到本机 FastAPI（`:8000`）。MySQL / Redis / Qdrant 用 `make middleware` 起在本机端口。

```mermaid
flowchart TB
  subgraph Client
    Browser[Browser]
  end

  subgraph App
    Web[web · Vite :5173]
    API[api · FastAPI :8000]
  end

  subgraph Workers
    MW[media-worker<br/>Celery -Q media]
    SW[studio-worker<br/>Celery -Q studio]
  end

  subgraph Data
    MySQL[(MySQL :3306)]
    Redis[(Redis :6379)]
    Qdrant[(Qdrant :6333)]
    FS[./storage · ./skills]
  end

  Browser --> Web
  Web -->|proxy /api| API
  API --> MySQL
  API --> Redis
  API --> Qdrant
  API --> FS
  API -->|enqueue| Redis
  Redis --> MW
  Redis --> SW
  MW --> MySQL
  MW --> FS
  MW --> Qdrant
  SW --> MySQL
  SW --> FS
```

## 组件

| 组件 | 职责 |
|------|------|
| **web** | React + Vite；开发期 `:5173`，代理 `/api` → api |
| **api** | FastAPI：鉴权、笔记本/来源/标签、聊天 SSE、知识底稿、发现检索、入队 |
| **media-worker** | 抓取、字幕、向量索引（`-Q media`） |
| **studio-worker** | 思维导图 / PPT（`-Q studio`，依赖本机 Claude CLI） |
| **MySQL** | 业务库（含 `tags` / `notebook_tags`） |
| **Redis** | 缓存 `db0`；Celery broker/result `db1`/`db2` |
| **Qdrant** | 语义检索 |
| **本地盘** | `STORAGE_ROOT=./storage`，`SKILLS_ROOT=./skills` |

## 主业务路径

```mermaid
flowchart LR
  A[加视频<br/>上传/URL/网页搜索] --> B[media-worker]
  B --> C[笔记本三栏]
  C --> D[对话 · 引用跳字幕]
  C --> E[知识底稿]
  E --> F[studio-worker<br/>导图/PPT]
  G[标签·自动整理] --> H[首页 Chip]
  C --> H
  I[公开] --> J[发现·关键词/语义]
```

1. 浏览器只访问 web；API 经代理。
2. 抓取 / ASR / 索引 / 导图 PPT 走 Celery，api 立即返回任务状态。
3. 标签存在 MySQL；自动整理只落库有关联的标签。
