# video-notebook · 设计文档

> 与 `docs/requirements.md` 配套。需求定型后写的设计方案。**改动需求前需先改 `requirements.md` 并经用户过目**；改动设计前需用户过目本文档。

**版本日期**：2026-10-16
**取代**：`docs/superpowers/specs/2026-10-15-video-notebook-design.md`（已撤回）。本版基于七轮决策拍板后定档。

---

## 1. 概览

video-notebook 是一个 Web SaaS，定位为「**视频专卖的 NotebookLM**」：

- **左/中/右三栏**对齐 NotebookLM，但 Source 收紧到视频。
- 视频持久存储于服务端对象存储（v1 本地磁盘），链接失效不影响笔记。
- 服务端 ASR（默认 OpenAI Whisper，adapter 化）为无字幕视频兜底。
- v1 检索走**全上下文**策略：把勾选来源的完整字幕 + 笔记拼成 prompt 喂给 LLM（minimax，Anthropic-兼容）。RAG 接口预留，**v1 不实现**。
- 笔记本作者可设「**分享全员**」，进入首页「发现」；其他登录用户只读访问。
- 后端可调度 claude code 进程加载 skill 完成复杂生成任务；v1 用于 PPT Studio（officecli-pptx skill）。

---

## 2. 技术栈（已锁定）

| 层 | 选型 | 备注 |
|---|---|---|
| 前端 | React 18 + TypeScript + Vite + shadcn/ui + Tailwind CSS | 三栏布局 + Discover + /admin |
| 后端 | FastAPI（Python 3.11+）+ Uvicorn | 异步 async/await |
| 任务队列 | Celery + Redis | 异步任务 worker 与 claude code 调度 |
| 数据库 | MySQL 8.x（utf8mb4 / UTC） | SQLAlchemy 2.x ORM |
| 迁移 | Alembic | 与 SQLAlchemy 同源 |
| 视频转码/抽音 | FFmpeg | 系统二进制，进程内调用 |
| URL 抓取 | yt-dlp | 子进程调用 |
| ASR | adapter 模式：Whisper（默认）/ 阿里云 / 字节 | 接口 `AsrAdapter` |
| LLM | minimax（Anthropic-兼容） | `anthropic` SDK 直连 |
| 对象存储 | 本地 FS + `ObjectStorage` 接口 | 预留 S3/R2/OSS |
| 播放器 | 原生 `<video>` + WebVTT cues | 字幕作为 native track 喂入 |
| Mind Map 渲染 | markmap（前端） | 输入 Markdown |
| PPT 生成 | **Claude Code 进程 + `officecli-pptx` skill**（admin 可在 `/admin/agents` 配置 skill + 模型 + 提示） | 通过 §8 AgentRunner 调度 |
| Mind Map 生成 | **Claude Code 进程**（admin 可在 `/admin/agents` 选其他配置；默认 skill_id=NULL） | 同上 |
| Skill 包存储 | **本地 FS `/data/skills/<id>/`** | zip 上传解压；管理员可扩展 |
| 鉴权 | JWT（access + refresh） | Refresh 7 天，access 2 小时 |
| 密码哈希 | bcrypt | 12 轮 |
| 部署 | docker-compose（v1） | 单机 / 内网 |
| 可观测性 | JSON 行日志 + docker healthcheck | v1 不上 Loki |

---

## 3. 系统架构分层

```
┌──────────────────────────────────────────────────────────────────┐
│                          Web Browser                              │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  React (SPA) · 三栏布局 · Discover · /admin               │   │
│  │  - shadcn/ui · Tailwind · markmap · <video> + cues        │   │
│  └────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
                              │ HTTPS
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                       API (FastAPI)                               │
│  - JWT 鉴权                                                         │
│  - 业务路由：auth / notebook / source / subtitle / chat /          │
│             studio / discover / collections / notes               │
│  - 后台路由：/admin/users / /admin/configs                         │
│  - 任务入队（Celery client）                                         │
│  - SSE 流式输出 chat                                                │
└──────────────────────────────────────────────────────────────────┘
                  │                │                │
                  ▼                ▼                ▼
        ┌─────────────┐   ┌──────────────┐   ┌──────────────┐
        │   MySQL     │   │    Redis     │   │   Object     │
        │  8.x utf8mb4│   │   (Celery    │   │  Storage     │
        │     UTC     │   │   broker +   │   │  (Local FS)  │
        │             │   │   result)    │   │  /data/...   │
        └─────────────┘   └──────────────┘   └──────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────┐
│                       Worker (Celery)                              │
│  - 队列：                                                          │
│    · asr  (字幕转写)                                                │
│    · fetch (yt-dlp URL 抓取)                                        │
│    · studio-mind-map (claude code dispatch)                        │
│    · studio-ppt (claude code dispatch)                             │
│  - Skill Dispatcher 子模块：spawn `claude` 进程 + skill            │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                  ┌──────────────────────────┐
                  │   Claude Code (subprocess)│
                  │   + skill (officecli-pptx)│
                  │   → PPTX file → /data    │
                  └──────────────────────────┘
```

### 3.1 服务清单（docker-compose）

| 服务 | 容器名 | 镜像基础 | 端口 |
|---|---|---|---|
| `web` | video-notebook-web | nginx 静态 + SPA fallback | 80 |
| `api` | video-notebook-api | python:3.11-slim + uvicorn | 8000（仅内网） |
| `worker` | video-notebook-worker | 同 api 镜像，CMD celery | – |
| `db` | video-notebook-mysql | mysql:8.0 | 3306（仅内网） |
| `redis` | video-notebook-redis | redis:7-alpine | 6379（仅内网） |
| `storage` | host volume | `/data/video-notebook` | – |

无 cloudflared / tunnel。

---

## 4. 模块划分

### 4.1 API 模块（FastAPI routers）

| 模块 | 路由前缀 | 主要职责 |
|---|---|---|
| `auth` | `/api/auth` | 登录、登出、修改密码、刷新 token |
| `users` | `/api/users` | 当前用户信息、改名、改密 |
| `notebooks` | `/api/notebooks` | CRUD、置顶、分享全员开关 |
| `sources` | `/api/sources` | 上传（分片）、URL 抓取、列表、删除、签名 URL |
| `subtitles` | `/api/subtitles` | 字幕读取、SRT 下载、触发重转 |
| `notes` | `/api/notes` | 笔记 CRUD、富文本保存 |
| `chat` | `/api/notebooks/{id}/chat` | 提问（SSE 流式）、保存为笔记、相关问题 |
| `studio` | `/api/notebooks/{id}/studio` | Mind Map / PPT 任务发起、查询、删除、产物下载 |
| `discover` | `/api/discover` | 公开笔记本列表 |
| `collections` | `/api/collections` | 自用集合 CRUD |
| `admin_users` | `/api/admin/users` | 用户管理（仅 admin） |
| `admin_configs` | `/api/admin/configs` | LLM / ASR 配置（仅 admin） |

### 4.2 共享子模块

| 子模块 | 路径（建议） | 职责 |
|---|---|---|
| `db` | `app/db` | SQLAlchemy session、模型 |
| `auth` | `app/core/security.py` | JWT 签发 / 校验、密码哈希、`require_user` / `require_admin` 依赖注入 |
| `multitenancy` | `app/core/owner.py` | `OwnerScopedSession`，所有查询过滤 `owner_id` |
| `object_storage` | `app/storage/` | `ObjectStorage` 接口 + `LocalFsStorage` |
| `asr` | `app/asr/` | `AsrAdapter` 接口 + `WhisperAdapter` + `AliyunAdapter`(stub) + `VolcengineAdapter`(stub) |
| `retrieval` | `app/retrieval/` | `RetrievalStrategy` 接口 + `FullContextStrategy` |
| `llm` | `app/llm/` | `LlmProvider` 接口 + `MinimaxProvider`（Anthropic SDK） |
| `agents` | `app/agents/` | `AgentRunner` 接口 + `ClaudeCodeRunner`；`services/skills.py` 处理 skill 上传 / 解压 / 校验；`services/agents.py` 处理 agent CRUD |
| `tasks` | `app/tasks/` | Celery 任务定义（ASR / fetch / studio-*） |
| `subtitle_chain` | `app/subtitles/chain.py` | embedded → platform → ASR 落库管线 |
| `models_config` | `app/configs/` | 模型配置读 DB（带内存缓存，配置变更后失效） |

---

## 5. 数据模型

> SQLAlchemy 风格简写。详细字段在实施时细化。

### 5.1 实体关系

```
users ─┬─< notebooks ─┬─< notebook_sources >── videos
       │              ├─< notes
       │              └─< chat_threads ─< chat_messages
       │              └─< studio_tasks
       ├─< collections ─< collection_notebooks >── notebooks
       └─< (admin 角色标记于 users.role)
```

### 5.2 表清单

| 表 | 关键列 | 备注 |
|---|---|---|
| `users` | id, phone (unique), name, password_hash, role(`user`/`admin`), status(`active`/`disabled`), created_at, last_login_at | phone 唯一；role 索引 |
| `notebooks` | id, owner_id, title, icon, cover_url, is_pinned, share_all(bool), created_at, updated_at, deleted_at | `owner_id` 索引；`share_all` 索引 |
| `videos` | id, owner_id, source_type(`upload`/`url`), source_url, storage_key, mime, duration_ms, width, height, size_bytes, content_hash, status(`pending`/`fetching`/`transcoding`/`uploading`/`ready`/`failed`), error_message, created_at | `owner_id + content_hash` 联合索引做去重 |
| `subtitles` | id, video_id, source(`embedded`/`platform`/`asr`), language (nullable), format(`srt`/`vtt`), storage_key, line_count, created_at, version | 字幕覆盖写时递增 version |
| `notebook_sources` | notebook_id, video_id, sort, selected_for_chat(bool), added_at | 联合主键 (notebook_id, video_id) |
| `notes` | id, notebook_id, author_id, title, content_json (富文本 JSON), created_at, updated_at, deleted_at | 由 chat message 保存来的也存这 |
| `chat_threads` | id, notebook_id, owner_id, last_message_at | 预留多轮会话；v1 同 notebook 共享 |
| `chat_messages` | id, thread_id, role(`user`/`assistant`/`system`), content_text, citations_json, source_ids, created_at | citations_json: [{ source_id, line_no, snippet }] |
| `studio_tasks` | id, notebook_id, **agent_id**(nullable), kind(`mind_map`/`ppt`), status, params_json, result_json, error_message, attempts, created_at, updated_at, finished_at | kind 索引 |
| `studio_mind_maps` | task_id, markdown, json_tree | mind_map kind 的产物 |
| **`skills`** | id, name (unique), description, version, **storage_path**, file_count, size_bytes, is_builtin, uploaded_by, created_at, updated_at, deleted_at | §8.2 上传解压到 `/data/skills/<id>/`；soft delete |
| **`agents`** | id, name, kind, provider(`claude_code`), skill_id (FK), model_name, system_prompt, params_json, timeout_seconds, is_default, is_active, updated_by, created_at, updated_at, **UNIQUE(kind, is_default)** | §8.2；Studio 任务创建时按 kind 走 default |
| `studio_slides` | task_id, file_storage_key, slide_count, mime(`pptx`/`pdf`) | ppt kind 的产物 |
| `collections` | id, owner_id, name, icon, created_at | |
| `collection_notebooks` | collection_id, notebook_id, added_at | 联合主键 |
| `llm_configs` | id, provider(`openai`/`anthropic`/`gemini`/`ollama`/`minimax`), base_url, api_key_enc, model_name, params_json, is_active(bool), updated_at, updated_by_user_id | v1 仅一条 `is_active=true`（全局默认） |
| `asr_configs` | id, provider(`whisper`/`aliyun`/`volcengine`), api_key_enc, model_size(`small`/`medium`/`large-v3`), language_policy(`auto`/`fixed`), fixed_language(nullable), is_active(bool), updated_at, updated_by_user_id | v1 仅一条 |
| `audit_admin_actions` | id, user_id, action, target, payload_json, created_at | v1 **不实现**；预留表 |
| Celery 标准 | celery_taskmeta / celery_taskresult | Celery 自带表 |

### 5.3 共享元数据

- **对象存储 layout**：`<root>/<yyyy>/<mm>/<sha1_prefix2>/<sha1>.ext`
- **字幕存储**：与原视频同级目录，`<video_key>.srt` 与 `<video_key>.json`（含每行行号 + 时间戳 + 文本）

---

## 6. API 表面

> 只列主要端点；详细请求 / 响应 schema 在 OpenAPI 自动生成（FastAPI 默认）。
> 所有 `/api/...` 端点都需要 JWT（除 `/api/auth/login`、`/api/auth/refresh`）。

### 6.1 认证与用户

```
POST /api/auth/login        { phone, password } → { access, refresh, user }
POST /api/auth/refresh      { refresh } → { access, refresh }
POST /api/auth/logout       (撤销 refresh)

GET   /api/users/me         → { id, name, phone, role }
POST  /api/users/me/change_password { old, new }
```

### 6.2 笔记本与笔记

```
GET    /api/notebooks?search=&page=&size=
POST   /api/notebooks       { title }
GET    /api/notebooks/{id}
PATCH  /api/notebooks/{id}  { title, icon, is_pinned }
DELETE /api/notebooks/{id}

POST   /api/notebooks/{id}/share_all     → 200
DELETE /api/notebooks/{id}/share_all     → 200

POST   /api/notebooks/{id}/notes         { content_json, title }
PATCH  /api/notes/{id}
DELETE /api/notes/{id}
GET    /api/notebooks/{id}/notes
```

### 6.3 视频与字幕

```
# 上传
POST  /api/sources/{notebook_id}/upload          multipart/form-data
                                                 → { video_id, task_id }
# URL 抓取
POST  /api/sources/{notebook_id}/fetch           { url }
                                                 → { video_id, task_id }

GET   /api/sources/{video_id}                    → 视频元数据 + 状态
DELETE /api/sources/{notebook_id}/{video_id}     → 删除（关联 notebook_source + 字幕 + 物理文件，若无其他 notebook 引用）

# 字幕
GET   /api/sources/{video_id}/subtitle           → { lines: [{ start_ms, end_ms, text }], version, source }
GET   /api/sources/{video_id}/subtitle.srt       → text/srt（直接下载）
POST  /api/sources/{video_id}/regenerate         → 触发重转任务 → { task_id }
GET   /api/sources/{video_id}/play_url           → { signed_url, expires_at }

GET   /api/sources/{notebook_id}                 → 该笔记本下的视频列表
PATCH /api/sources/{notebook_id}/{video_id}      { selected_for_chat: bool }
```

### 6.4 对话

```
POST /api/notebooks/{id}/chat                    { message, source_ids: [video_id, ...] }
                                                → SSE 流，每条 event:
                                                  · token 增量
                                                  · citations: [{ source_id, line_no, snippet }]
                                                  · done
POST /api/messages/{id}/save_as_note             { title? } → { note_id }
POST /api/notebooks/{id}/related_questions       → { questions: [...] }
GET  /api/notebooks/{id}/chat_history?cursor=
```

> **SSE 实现**：`fastapi.responses.StreamingResponse`，内部 `RetrievalStrategy.build_context()` 拼上下文，`LlmProvider.stream_chat(prompt)` 流式。

### 6.5 Studio

```
# Mind Map
POST /api/notebooks/{id}/studio/mind_map       { source_ids, topic, language?, agent_id? }
                                              → { task_id }
GET  /api/studio/tasks/{id}                   → { status, result?, agent_id, agent_name }
DELETE /api/studio/tasks/{id}                 → 取消任务

GET /api/studio/mind_maps/{id}                → { markdown, json_tree, sources }

# Slide
POST /api/notebooks/{id}/studio/slides        { source_ids, prompt, language?, agent_id? }
                                              → { task_id }
GET  /api/studio/slides/{id}/download         → { signed_url }
```

### 6.6 Discover / Collections

```
GET  /api/discover/notebooks?search=&page=    → 仅返回 share_all=true 的公开列表（已登录）
GET  /api/discover/notebooks/{id}             → 只读视图详情

GET  /api/collections
POST /api/collections                          { name, icon }
DELETE /api/collections/{id}
POST /api/collections/{id}/notebooks           { notebook_id }
DELETE /api/collections/{id}/notebooks/{nb_id}
```

### 6.7 Admin

#### 用户管理

```
GET    /api/admin/users?search=&page=
POST   /api/admin/users                         { phone, name, password, role }
POST   /api/admin/users/{id}/reset_password     { new_password }
POST   /api/admin/users/{id}/disable
POST   /api/admin/users/{id}/enable
```

#### 模型配置

```
GET    /api/admin/configs/llm
PUT    /api/admin/configs/llm                   { provider, base_url, api_key, model_name, params? }
GET    /api/admin/configs/asr
PUT    /api/admin/configs/asr                   { provider, api_key, model_size?, language_policy?, fixed_language? }
```

#### Skills 管理（§8 Agent 设计的一部分）

```
GET    /api/admin/skills?search=&page=
POST   /api/admin/skills                        multipart `file=skill.zip` → { id, name, ... }
GET    /api/admin/skills/{id}                   → { id, name, description, version, file_count, size_bytes, is_builtin, ... }
PATCH  /api/admin/skills/{id}                   { name?, description?, version? }     # 仅元数据
POST   /api/admin/skills/{id}/download         → skill_<id>.zip
DELETE /api/admin/skills/{id}                   → 软删（仅当无 Agent 引用；is_builtin=true 不允许删）
```

#### Agents 管理（§8 Agent 设计的一部分）

```
GET    /api/admin/agents?kind=&page=
POST   /api/admin/agents                        { name, kind, provider(claude_code), skill_id?, model_name?, system_prompt?, params_json?, timeout_seconds?, is_default? }
GET    /api/admin/agents/{id}
PATCH  /api/admin/agents/{id}                   {...}
POST   /api/admin/agents/{id}/set_default       → 把同 kind 之前的 default 改成 false，再置本条为 true
POST   /api/admin/agents/{id}/disable
POST   /api/admin/agents/{id}/enable
DELETE /api/admin/agents/{id}                   → 禁用而非真删
```

---

## 7. 任务管线

### 7.1 视频上传与字幕

```
upload (multipart) ─┐
                    ├─► videos.status=pending  ─► Celery fetch task
url paste ──────────┘                            │
                                                  │ yt-dlp → mp4 → storage
                                                  ▼
                                            videos.status=ready
                                                  │ (无字幕轨道)
                                                  ▼
                                       Celery asr task (Whisper)
                                                  │
                                                  ▼
                                            subtitles 入库
                                                  │
                                                  ▼
                                     sources 列表显示「已就绪」
```

**S2.4 字幕来源链顺序**：
1. **embedded**：ffprobe 检测原视频是否携带字幕轨道 → 若有，ffmpeg 抽 SRT → 入库 `source=embedded`；
2. **platform**：仅当 source_type=url 且 yt-dlp 拿回了平台字幕 → 入库 `source=platform`；
3. **asr**：上述两条都没 → 自动调度 Celery asr 任务，调用当前 ASR 配置。

### 7.2 ASR Worker

```
@celery_app.task(name='asr.transcribe', bind=True, max_retries=3)
def transcribe(self, video_id: int):
    config = AsrConfigService.get_active()         # 从 DB 读
    adapter = AsrAdapterFactory.create(config)     # 选 Whisper / Aliyun / Volc
    src = storage.get_signed_url(video.storage_key)
    job = adapter.submit(src, model_size=...)
    while not job.done():
        sleep(2); job.refresh()
    srt, json = adapter.fetch_result(job)
    storage.put(srt_key, srt)
    storage.put(json_key, json)
    db.upsert_subtitle(video_id, source='asr', ...)
```

### 7.3 Studio 任务

```
@celery_app.task(name='studio.ppt', bind=True)
def ppt_task(self, notebook_id, params):
    task = StudioTask(kind='ppt', notebook_id, params)
    task.mark_running()

    inputs = build_skill_inputs(notebook_id, params['source_ids'], params['prompt'])
    # Skill Dispatcher 在 Celery worker 进程内 spawn `claude` 子进程
    result_path, logs = await skill_dispatcher.run(
        skill='officecli-pptx',
        inputs=inputs,
        timeout=600,
    )
    # 把产物移到对象存储
    storage_key = storage.put(result_path)
    Slides.create(task_id=task.id, storage_key=..., mime='pptx', slide_count=...)
    task.mark_succeeded(result={'storage_key', 'slide_count'})
```

### 7.4 重转与重生成

- **重转字幕**：`POST /sources/{id}/regenerate` → Celery asr 任务 → 完成后 `subtitles` 插入新 version 记录，旧版默认删（v1）。
- **重做 Studio**：用户从前端删任务即可，无独立「重做」端点（避免状态机复杂度）。

---

## 8. Agent + Skill 设计

> **v1.1 设计变更**：把原来的「Skill Dispatcher 内置 skill 名」改成 **Agent 与 Skill 解耦** 的模型。
> - **Skill** 是被上传的文件包（zip，解压后含 `SKILL.md`），落本地文件系统。
> - **Agent** 是管理员配置的「由哪个 provider 跑哪个 skill」。Agent 引用 Skill，外加 model、system_prompt、超参等。
> - Studio 任务可以选择某个 Agent（**默认走当前 `kind` 的 `is_default=true` Agent**），调度抽象就是「按 Agent 配置 spawn provider 子进程」。

### 8.1 概念

```
Skill（管理员上传 zip 解压后落 /data/skills/<id>/）
   │
   │  skill_id (FK)
   ▼
Agent（管理员配置）
   ├─ name（"PPT Agent" / "Mind Map Agent" / ...）
   ├─ kind（mind_map / ppt / other）
   ├─ provider（v1 锁 claude_code）
   ├─ skill_id ─► Skill
   ├─ model_name（如 claude-sonnet-4-6 / claude-opus-4-8）
   ├─ system_prompt（追加在 SKILL.md 后）
   ├─ params_json（透传 CLI 参数）
   ├─ timeout_seconds
   └─ is_default（每个 kind 最多 1 个）

Studio 任务
   ├─ agent_id （NULL 时取 kind 的默认）
   ├─ kind
   ├─ params (用户输入：source_ids, prompt, language)
   └─ 调用 AgentRunner.run_agent(agent_id, inputs)
```

### 8.2 数据模型（追加到 §5.2 表清单）

```sql
CREATE TABLE skills (
  id              INT PRIMARY KEY AUTO_INCREMENT,
  name            VARCHAR(64) UNIQUE NOT NULL,
  description     TEXT,
  version         VARCHAR(32),
  storage_path    VARCHAR(255) NOT NULL,   -- /data/skills/<id>/
  file_count      INT,
  size_bytes      BIGINT,
  is_builtin      BOOLEAN DEFAULT FALSE,   -- 内置 skill 不可删
  uploaded_by     INT NOT NULL,
  created_at      DATETIME,
  updated_at      DATETIME,
  deleted_at      DATETIME,
  INDEX (deleted_at)
);

CREATE TABLE agents (
  id              INT PRIMARY KEY AUTO_INCREMENT,
  name            VARCHAR(64) NOT NULL,
  kind            ENUM('mind_map','ppt','other') NOT NULL,
  provider        ENUM('claude_code') NOT NULL DEFAULT 'claude_code',
  skill_id        INT,
  model_name      VARCHAR(64),
  system_prompt   TEXT,
  params_json     JSON,
  timeout_seconds INT DEFAULT 600,
  is_default      BOOLEAN DEFAULT FALSE,
  is_active       BOOLEAN DEFAULT TRUE,
  updated_by      INT,
  created_at      DATETIME,
  updated_at      DATETIME,
  UNIQUE KEY uniq_default_per_kind (kind, is_default),  -- 每 kind 唯一 default
  FOREIGN KEY (skill_id) REFERENCES skills(id)
);

-- studio_tasks 加列
ALTER TABLE studio_tasks
  ADD COLUMN agent_id INT,
  ADD FOREIGN KEY (agent_id) REFERENCES agents(id);
```

### 8.3 AgentRunner 接口

```python
# app/agents/runner.py
class AgentRunner:
    async def run_agent(
        self,
        agent_id: int | None,         # None 时按 studio_task.kind 取默认 Agent
        kind: str,
        inputs: dict,
        on_progress: Callable[[int, str], None] | None = None,  # (percent, msg)
    ) -> AgentRunResult: ...

@dataclass
class AgentRunResult:
    run_id: str
    outputs: list[OutputArtifact]   # 主产物 + （可选）副产物
    structured_output: dict | None
    duration_ms: int
    logs_excerpt: str

@dataclass
class OutputArtifact:
    role: str                       # 'main' | 'side'
    storage_key: str
    filename: str
    mime: str
    size_bytes: int
    meta: dict                      # 来自 MANIFEST.json
```

### 8.4 实现骨架（`ClaudeCodeRunner`）

```python
class ClaudeCodeRunner:
    def __init__(self, claude_cli_path='claude', skills_root='/data/skills'):
        self.claude_cli = claude_cli_path
        self.skills_root = Path(skills_root)

    async def run_agent(self, agent, inputs, timeout, on_progress):
        # 1. 准备 work_dir
        work_dir = Path(tempfile.mkdtemp(prefix='agent_'))
        inputs_path = work_dir / 'inputs.json'
        outputs_dir = work_dir / 'outputs'
        outputs_dir.mkdir()
        inputs_path.write_text(json.dumps(inputs, ensure_ascii=False))

        # 2. 解析 skill 目录（Agent.skill_id 可为空：不指定 skill，直接与 claude 对话）
        if agent.skill_id is None:
            skill_arg = []
            skill_md = ''
        else:
            skill = Skill.get(agent.skill_id)
            skill_dir = Path(skill.storage_path)
            skill_md = (skill_dir / 'SKILL.md').read_text() if (skill_dir / 'SKILL.md').exists() else ''
            skill_arg = ['--skill-dir', str(skill_dir)]

        # 3. 拼最终 prompt = SKILL.md + agent.system_prompt + 入参描述
        prompt = self._build_prompt(skill_md, agent.system_prompt, inputs_path)

        # 4. spawn `claude`
        cmd = [
            self.claude_cli,
            *skill_arg,
            '--model', agent.model_name,
            '--inputs-json', str(inputs_path),
            '--workdir', str(work_dir),
            '--output-manifest', str(outputs_dir / 'MANIFEST.json'),
        ] + self._extra_params(agent.params_json) + [prompt]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(work_dir),
            start_new_session=True,        # 杀进程时连带子进程
            env={**os.environ, 'CLAUDE_CODE_RUN_ID': work_dir.name},
        )

        # 5. 限时 + 进度回调
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout)
        except asyncio.TimeoutError:
            os.killpg(proc.pid, signal.SIGTERM)
            await asyncio.sleep(5)
            if proc.returncode is None:
                os.killpg(proc.pid, signal.SIGKILL)
            raise AgentTimeout(agent.id, timeout)

        # 6. 取产物
        artifacts = self._collect_artifacts(outputs_dir, work_dir / 'MANIFEST.json')

        return AgentRunResult(
            run_id=work_dir.name,
            outputs=artifacts,
            structured_output=None,
            duration_ms=...,
            logs_excerpt=(stdout[-2000:] if stdout else '').decode(errors='ignore'),
        )

    def _collect_artifacts(self, outputs_dir, manifest_path) -> list[OutputArtifact]:
        """产物捕获契约，详见 §8.5"""
        ...
```

### 8.5 **产物捕获契约**（核心可靠性设计）

#### 8.5.1 Skill 侧约定（写进每个 SKILL.md）

Skill 包内的 `SKILL.md` 必须包含如下强制约定片段（管理员上传时由后端校验；内置 skill 包预置此约定）：

```
## 输出约定（强制）
所有产物必须写到当前工作目录下的 `outputs/` 子目录。
完成后必须写 `outputs/MANIFEST.json`，结构：

```json
{
  "version": 1,
  "status": "success" | "partial" | "failed",
  "artifacts": [
    {
      "role": "main" | "side",
      "path": "outputs/your-main-file.pptx",
      "mime": "<MIME>",
      "meta": { "...": "额外的字段，如 slide_count" }
    }
  ],
  "notes": "可选说明"
}
```

如果 `<role=main>` 的产物缺失，必须把 `status` 写成 `failed`，并在 `notes` 给出原因。
```

**上传校验**：`POST /api/admin/skills` 后端拒收任何不含 `SKILL.md` 的 zip；并对 `SKILL.md` 做最小 frontmatter 校验（description、version 可选），缺少 `## 输出约定` 章节时给警告但允许上传（后续产物的契约兜底已在 wrapper 完成）。

#### 8.5.2 Wrapper 侧容错（六层保险）

```
[ claude 进程退出 ]
  │
  ├─ exit_code != 0
  │    └─ 任务失败；error_message = stderr 末 2K
  │
  └─ exit_code == 0
       │
       ├─ 1. 读 outputs/MANIFEST.json
       │    ├─ 存在 & status='success' & 至少 1 个 role='main' → ✅ 直接采用
       │    ├─ 存在 & status='partial'  → ⚠️ 采用 artifacts[]，但记 warns
       │    ├─ 存在 & status='failed'   → ❌ 任务失败，notes 进 error_message
       │    └─ 不存在 / JSON 损坏 → 进入兜底扫描
       │
       ├─ 2. 兜底扫描（manifest 缺失 / 不可解析时）
       │    ├─ list outputs/* 排除 0 字节文件
       │    ├─ 后缀推断 mime
       │    ├─ 取**体积最大**的文件作为主产物
       │    │    └─ 主产物 ≥ 5KB → ✅ 视为成功
       │    └─ 否则 → ❌ 失败，error = "no_output"
       │
       └─ 3. 把 artifacts 从 work_dir 拷到对象存储
            └─ storage_key = studio_outputs/<task_id>/<uuid>.<ext>
```

#### 8.5.3 进程级可靠性

| 保险层 | 触发 | 处理 |
|---|---|---|
| L1 心跳 | 30 秒内 stdout 无新数据 | on_progress(percent, msg) 推一次 |
| L2 硬超时 | 到达 `agent.timeout_seconds` | SIGTERM → 5s 后 SIGKILL（连同进程组）→ `failed=timeout` |
| L3 manifest | 进程退出有 manifest | 见 §8.5.2 |
| L4 兜底扫描 | manifest 缺失 / 不可解析 | 见 §8.5.2 |
| L5 主产物缺失 | 兜底也没主产物 | `failed=no_output` |
| L6 自动重试 | Studio wrapper 内 1 次自动重试 | 复用 inputs，新建 work_dir，再走一遍（避免残留进程状态干扰） |

注：v1 默认「不」自动重试；L6 留接口位，由管理员在 Agent 配置里加 `max_retries` 后启用，**v1 写 0**。

#### 8.5.4 work_dir 隔离与清理

- 每个 AgentRun 独立 `work_dir`，**路径用 uuid**：`<temp_root>/agent_<uuid>/`
- `start_new_session=True` 让 `claude` 进程自成一组，kill 时连同 shell/子进程一起收。
- stdout/stderr 同时 tee 到 `work_dir/{stdout,stderr}.log`（按 ≥ 1MB rotate，超 50MB 截断）。
- 任务结束（无论成败）后**延迟 4 小时清理** work_dir，便于失败排查；清理 worker 跑在 Celery beat 上。

### 8.6 Admin UI（与 §6.7 配合）

#### `/admin/skills`
- 表格列：name / version / 大小 / 来源（内置/上传）/ 上传时间
- 操作：
  - **上传 Skill**：`POST /api/admin/skills` multipart(`file=skill.zip`)。后端校验：含 `SKILL.md` 才接受；解压到 `/data/skills/<新id>/`。
  - **下载 Skill**：把目录再打 zip 下发。
  - **编辑元数据**：name / description / version（不影响目录内容）。
  - **删除**：软删（仅当无 Agent 引用）。`is_builtin=true` 的不允许删。

#### `/admin/agents`
- 表格：name / kind / provider / skill 名 / model / 默认 / 启用
- 操作：
  - **新建 Agent**：表单字段 = §8.2 schema 列。`kind` 下拉、`skill_id` 下拉（拉 `/admin/skills`）。
  - **编辑 Agent**：同表单。
  - **设为默认**：每个 kind 只能 1 个；切换 default 时同时把上一个 default 设为 false。
  - **启用 / 停用**：停用后 Studio 不再可选。

### 8.7 与现有 §6.5/§6.7 的关系

- §6.5 Studio API：`POST /api/notebooks/{id}/studio/{kind}` 新增可选 body `agent_id`；不传 = 走 `kind` 默认 Agent。
- §6.7 Admin API（详见新版）：
  - `GET/POST/PATCH/DELETE /api/admin/skills` + `POST /api/admin/skills/{id}/download`
  - `GET/POST/PATCH/DELETE /api/admin/agents` + `POST /api/admin/agents/{id}/set_default`

### 8.8 迁移 / 种子数据

- 启动迁移：
  - 创建 `skills` / `agents` 表。
  - `studio_tasks.agent_id` 列加 nullable。
- **首次启动 seed**：
  - 内置 skill：`name='officecli-pptx'`、`is_builtin=true`，`storage_path=/opt/vnb/builtin-skills/officecli-pptx/`（镜像内置），不允许删。
  - 内置 agents：
    - `name='PPT Agent'`、`kind=ppt`、`provider=claude_code`、`skill_id=<上述>`、`is_default=true`。
    - `name='Mind Map Agent'`、`kind=mind_map`、`provider=claude_code`、`skill_id=NULL`、`model_name=claude-sonnet-4-6`、`is_default=true`（不传 skill 也能跑，让 claude 直接生成 markmap markdown）。

### 8.9 工程注意

- `claude` CLI 必须在 worker 容器镜像内（Dockerfile `npm i -g @anthropic-ai/claude-code` 或 bind mount）。
- LLM 默认 key 与 Claude Code key **不冲突**：
  - minimax 走 `LLM_*` env（minimax Anthropic-兼容 base url）。
  - claude code 读 `ANTHROPIC_API_KEY` env。
- 进程池：Celery worker `-c studio-mind-map studio-ppt`，每个队列并发建议 4（claude code 跑起来 IO 重，单 worker 内再多串行）。
- v1 **先忽略**：「Skill 商店」「Skill 评分」「Skill 版本回滚」「per-user 默认 Agent」。
- **多 main 产物**：v1 一个任务**只**取一个 main 产物（PPT 取 pptx、Mind Map 取 md），副产物保留为 evidence（暂不展示给用户）。

---

## 9. 前端结构

### 9.1 路由

```
/                              → 首页（笔记本列表）
/discover                      → 全员公开笔记本列表（已登录可访问）
/collections                   → 我的集合
/notebooks/:id                 → 笔记本（三栏）
/notebooks/:id/notebook-public → 公开笔记本的只读视图（从 /discover 进入）
/login                         → 登录页
/admin                         → 后台首页（admin 角色）
/admin/users                   → 用户管理
/admin/configs                 → 模型配置
/admin/configs/llm             → LLM 配置表单
/admin/configs/asr             → ASR 配置表单
```

### 9.2 三栏布局（`/notebooks/:id`）

```
┌─────────────────────────────────────────────────────────────────────┐
│  ← 返回首页 │ <notebook title>           │  …菜单 │ + │            │
├────────────┬────────────────────────────────┬────────────────────────┤
│  左栏       │           中栏                 │        右栏             │
│ (sources)   │         (chat)                 │       (studio)         │
│             │                                │                        │
│ [+ 来源]    │ [输入框 提问/让它生成点什么]    │ [思维导图][幻灯片]      │
│ [视频]      │ #N 用了 X 个来源                │ ─────                  │
│  ☐ video-1 │                                │ 最近任务列表            │
│  ☐ video-2 │                                │  ✓ Mind Map: ..         │
│ [笔记]      │                                │  ⟳ PPT (进度 60%)      │
│  ☐ note-1  │                                │  ✓ PPT: ..              │
└────────────┴────────────────────────────────┴────────────────────────┘
```

### 9.3 关键组件

- `<VideoPlayer>`：原生 `<video>` + WebVTT cues；接收 `selectedLineIndex` prop，外部点击字幕行时由父组件传入高亮行号。
- `<SubtitleList>`：渲染 SRT/JSON 为可点击行列表；行号 → 时间戳映射。
- `<ChatStream>`：消费 SSE，自动渲染编号引用 hover + click 事件（click 调用父组件的「跳字幕行」行为）。
- `<StudioTaskList>`：轮询任务状态。
- `<MindMapView>`：消费 markdown，调用 markmap 渲染。
- `<SourcesSidebar>`：checkbox + 选中状态 + 拖拽排序。

### 9.4 Discover 视图

只读路由 `/notebooks/:id?view=public`：
- 左栏：视频可播放，字幕可点但**禁用编辑器**；
- 中栏：历史问答只读，**输入框 disabled**；遇到 admin `share_all` 已关闭 → 立即回退到 404。

### 9.5 admin 后台

- `/admin/users`：表格列（手机号、姓名、角色、状态、最后登录、操作）
- `/admin/configs/llm`：表单（provider、base_url、api_key、model_name、params）
- `/admin/configs/asr`：表单（provider、api_key、model_size、语言策略）
- `/admin/skills`：§8.6；表格 + 上传 zip + 编辑元数据 + 下载 zip + 软删
- `/admin/agents`：§8.6；表格 + 新建/编辑表单（kind 下拉、skill_id 拉已上传列表、model、system_prompt、默认/启用开关）

---

## 10. 关键交互：前后端契约

### 10.1 上传视频

```
浏览器 → POST /sources/{notebook_id}/upload (multipart, file=...) [或分片]
                                            │
                                            ▼
                                   写 videos 行(status=pending)
                                            │
                                            ▼
                            Celery fetch任务 (仅 url 路径需要)；上传路径直接落本地存储
                                            │
                                            ▼
                                storage.put(videos.storage_key, ...)
                                            │
                                            ▼
                              videos.status=ready
                                            │
                                            ▼ (无字幕时)
                                  Celery asr 任务调度
                                            │
                                            ▼
                              前端轮询任务状态(GET /tasks/{id})
                                            │
                                            ▼
                              字幕就绪 → 通知前端刷新左栏列表
```

### 10.2 对话（SSE 流）

```
浏览器 → POST /api/notebooks/{id}/chat { message, source_ids }
                          │
                          ▼
            RetrievalStrategy.build_context(query, source_ids)
                          │   → { prompt_text, used_sources }
                          ▼
            LlmProvider.stream_chat(prompt_text)  (minimax Anthropic-SDK)
                          │
                          ▼
            SSE stream:
              data: {"type":"token", "t":"...轮"}
              data: {"type":"citation", "source_id":..., "line_no":..., "snippet":"..."}
              data: {"type":"done", "message_id":..., "tokens":...}
                          │
                          ▼
            前端流式更新消息；遇到 citation 入库用于悬浮预览。
            60K 软上限：build_context 返回 token 总数；超限 → SSE 首条 event:
              data: {"type":"warning", "code":"context_too_large", "tokens":...}
```

### 10.3 Studio PPT

```
浏览器 → POST /api/notebooks/{id}/studio/slides { source_ids, prompt, language, agent_id? }
                          │
                          ▼
                StudioTask(status=queued, agent_id=?)
                          │  (agent_id 缺省 → 查 kind='ppt' 的默认 Agent)
                          ▼
                Celery studio-ppt 任务
                          │
                          ▼
                AgentRunner.run_agent(agent, inputs={sources, prompt, language})
                          │
                          ▼
                ClaudeCodeRunner.spawn(work_dir=agent_<uuid>/)
                          │     ├── inputs.json + outputs/ 准备好
                          │     ├── skill_dir = Agent.skill.storage_path   # 内置 / 上传
                          │     ├── prompt = SKILL.md + Agent.system_prompt + 入参
                          │     └── claude --skill-dir ... --output-manifest outputs/MANIFEST.json
                          │
                          ▼
                  claude 子进程运行，写 outputs/<main>.<ext> + MANIFEST.json
                          │
                          ▼
                _collect_artifacts() 走 §8.5.2 六层保险
                          │
                          ▼
                storage.put(pptx, ...) → studio_slides.storage_key
                          │
                          ▼
                StudioTask(status=succeeded, result={slide_count, storage_key})
                          │
                          ▼
            前端轮询 → 点开 → /api/studio/slides/{id}/download → signed_url
```

---

## 11. 部署（docker-compose）

### 11.1 docker-compose.yml 关键片段（建议）

```yaml
services:
  web:
    image: nginx:alpine
    volumes:
      - ./web/dist:/usr/share/nginx/html:ro
      - ./web/nginx.conf:/etc/nginx/conf.d/default.conf:ro
    ports: ["80:80"]
    depends_on: [api]

  api:
    build: ./api
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
    env_file: .env
    depends_on: [db, redis]
    volumes:
      - ./storage:/data/video-notebook        # 视频 / 字幕 / Studio 产物
      - ./skills:/data/skills                  # 管理员上传的 skill 包（共享读）

  worker:
    build: ./api
    command: celery -A app.tasks.celery_app worker -Q fetch,asr,studio-mind-map,studio-ppt -c 4
    env_file: .env
    depends_on: [db, redis]
    volumes:
      - ./storage:/data/video-notebook
      - ./skills:/data/skills                  # 必须与 api 共享，否则 Skill ID 找不到目录
      # claude CLI 二进制挂载或镜像内安装
      - /usr/local/bin/claude:/usr/local/bin/claude:ro

  db:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: video_notebook
      MYSQL_USER: ${MYSQL_USER}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
    volumes:
      - mysql_data:/var/lib/mysql
    command: --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci --default-time-zone=+00:00

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data

volumes:
  mysql_data:
  redis_data:
```

### 11.2 环境变量（`.env.example`）

```bash
# 数据库
MYSQL_ROOT_PASSWORD=changeme
MYSQL_USER=vnb
MYSQL_PASSWORD=changeme
MYSQL_HOST=db

# Redis
REDIS_URL=redis://redis:6379/0

# JWT
JWT_SECRET=change-this-to-random
JWT_ACCESS_TTL_SECONDS=7200
JWT_REFRESH_TTL_SECONDS=604800

# LLM 默认
LLM_PROVIDER=minimax
LLM_BASE_URL=https://api.minimax.chat/v1   # Anthropic-兼容 base url
LLM_API_KEY=sk-...
LLM_MODEL_NAME=...
LLM_PARAMS_JSON={"temperature":0.2,"max_tokens":8192}

# ASR 默认
ASR_PROVIDER=whisper
ASR_API_KEY=sk-...
ASR_MODEL_SIZE=large-v3
ASR_LANGUAGE_POLICY=auto

# Claude Code (Studio 用)
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_CLI_PATH=/usr/local/bin/claude

# 模型配置 AES 主密钥（DB 内 api_key_enc 解密）
MASTER_SECRET=...

# 首个管理员 seed（容器首次启动时检测到无 admin 则创建）
SEED_ADMIN_PHONE=13800000000
SEED_ADMIN_PASSWORD=changeme-on-first-login
```

---

## 12. 首个管理员 Seed 机制

**做法**：env seed。

实现要点：
- 在 `app/main.py` 的 FastAPI lifespan 中：
  ```python
  @asynccontextmanager
  async def lifespan(app: FastAPI):
      await init_db()              # 创建表（如果 alembic 已跑，可跳过）
      await seed_admin_if_empty()  # 检测 + 创建
      yield
      await shutdown_resources()
  ```
- `seed_admin_if_empty()` 逻辑：
  ```python
  async def seed_admin_if_empty():
      phone = os.getenv('SEED_ADMIN_PHONE')
      password = os.getenv('SEED_ADMIN_PASSWORD')
      if not phone or not password:
          return
      existing = await User.count(role='admin')
      if existing > 0:
          return
      user = User(phone=phone, role='admin', name='Seed Admin', status='active')
      user.set_password(password)
      db.add(user)
      await db.commit()
      logger.info(f"Seeded admin user: {phone}")
  ```
- **安全注释**：在 `README` 中明确「**首次部署后请立刻修改 `SEED_ADMIN_PASSWORD` 对应账号的密码**」。

---

## 13. v1 不做（继承自 `requirements.md`）

- 字幕行内文本编辑（错误靠重新转写）
- RAG / 向量索引 / BM25 / 切片 / 重排序
- 点击字幕跳视频帧（仅跳字幕行）
- 受邀协作者 / 按手机号单独邀请 / 「与我共享」区域 / 多人实时协作
- 公开笔记本的写权限（只读）
- 计费 / 配额 / 付费档
- 自助注册 / 短信验证 / 密码找回
- 集合多人共享
- 详细审计 / RBAC 细分
- S3/R2/OSS（接口预留）
- 公网暴露 / 反向代理 / Cloudflare Tunnel
- CI/CD（手动部署）
- Loki + Prom + Grafana 完整可观测性
- v2 才做的：Mind Map 改用专门 skill（当前依赖默认对话）

**Agent + Skill 相关 v1 不做**（§8）：
- Skill 商店 / Skill 评分
- Skill 版本回滚 / 多版本并存
- per-user 默认 Agent（v1 仅全局「每个 kind 一个 default」）
- 多 main 产物的展示（v1 一个任务只展示一个主产物）
- Skill 自动重试（v1 留接口位，max_retries 默认 0）
- Agent 启动参数动态生效以外的能力（如 agent 自定义执行器、自定义超时策略）

---

## 14. 实施阶段待办（next step）

进入实现阶段时按以下顺序开工：

1. **脚手架 + 部署底座**
   - `api/` FastAPI 项目结构、依赖、`pyproject.toml` / `requirements.txt`
   - `web/` Vite + React + shadcn/ui 初始化
   - `docker-compose.yml` + `.env.example`
   - `Dockerfile`（api 与 worker 同一镜像）
   - `alembic init` & 第一个迁移
   - 首个管理员 seed 与 healthcheck

2. **鉴权与账号**
   - User model + JWT
   - 登录 / 刷新 / 修改密码
   - admin `/api/admin/users` CRUD
   - 前端 login 页 + 受保护路由

3. **模型配置**
   - `llm_configs` / `asr_configs` 表 + 加密层（AES-GCM）
   - `LlmProvider` 接口 + `MinimaxProvider`
   - `AsrAdapter` 接口 + `WhisperAdapter`（先实现唯一个）+ Aliyun/Volc stub
   - `/api/admin/configs/*` + 前端表单

4. **笔记本 + 来源基础**
   - Notebook CRUD
   - 上传（multipart，先做不分片，验证链路通顺再加分片）
   - 对象存储 LocalFs
   - 视频与 notebook 关联

5. **URL 抓取与字幕链**
   - Celery fetch 任务 + yt-dlp 集成
   - ffmpeg 抽字幕
   - 字幕表 + SRT 下载

6. **ASR 流水线**
   - Celery asr 任务
   - 配置动态加载（DB）
   - 重转按钮 + 任务面板

7. **聊天**
   - `RetrievalStrategy` 接口 + `FullContextStrategy`
   - `LlmProvider.stream_chat` + SSE
   - 引用编号入数据库
   - 60K 软上限提示
   - 保存为笔记、相关问题

8. **Skills 管理（§8.6）**
   - `skills` 表 + alembic migration
   - zip 上传、解压、SKILL.md 校验
   - 内置 skill 种子数据（`officecli-pptx`，镜像内置）
   - `/api/admin/skills` + 前端 `/admin/skills`

9. **Agents 管理 + AgentRunner（§8.4-§8.5）**
   - `agents` 表 + alembic migration
   - `studio_tasks.agent_id` 列
   - `AgentRunner` 接口 + `ClaudeCodeRunner` 实现
   - 产物捕获契约 §8.5 落地（含 manifest 解析、兜底扫描、work_dir 隔离）
   - `/api/admin/agents` + 前端 `/admin/agents`
   - 内置两个默认 agent 种子数据（PPT Agent / Mind Map Agent）

10. **Studio Mind Map**
    - Celery `studio-mind-map` 任务，调 AgentRunner（默认 Agent）
    - markmap 前端渲染
    - 任务面板显示 Agent 名称 + 状态

11. **Studio PPT（officecli-pptx）**
    - Celery `studio-ppt` 任务，调 AgentRunner（默认 PPT Agent）
    - 产物经 §8.5 捕获后落到对象存储
    - 下载链接

12. **Discover + Collections**
    - 分享全员开关 + Discover 列表
    - 只读视图组件
    - Collections CRUD

13. **打磨**
    - 错误处理 / 重试
    - 日志
    - 集成测试 / e2e 至少 3 个 happy path（含「上传 skill → 建 Agent → 跑 Studio → 下载产物」完整链路）
    - 用户文档（README）

---

## 15. 设计与需求一致性自检

| 需求条款 | 设计落地 |
|---|---|
| 三栏布局 | §9.2 |
| 视频来源（上传/URL/粘贴文字） | §7.1、§6.3 |
| 字幕链 (embedded→platform→asr) | §7.1、§7.2 |
| 自动检测语言 | §11.2 `ASR_LANGUAGE_POLICY=auto` |
| 重转字幕 | §6.3、§7.4 |
| SRT 下载 | §6.3、§5.2 |
| 空字幕兜底 | §7.1 字幕源链 + §9.5 来源页「暂无字幕」 |
| 全上下文检索 | §6.4、§7.x RetrievalStrategy |
| 60K 软上限 | §10.2 |
| 工作室（思维导图 + 幻灯片） | §6.5、§7.3、§8 |
| 点击引用跳字幕行 | §9.2、§10.2 |
| 邀请读写 / 分享全员只读 | §6.6、§9.4（v1 仅 share_all） |
| 管理员创建账号 | §6.1、§11.2、§12 |
| 管理员配置模型 | §6.7、§11.2、§14.3 |
| **管理员可配置 Agent（绑定 claude code + skill）** | **§6.7、§8.6、§14.9（Skills + Agents 全流程）** |
| **Skill 可上传** | **§6.7 `POST /api/admin/skills`、§8.6、§14.8** |
| **产物准确捕获** | **§8.5 契约 + 六层保险、§10.3** |
| 多租户 owner_id 隔离 | §4.2 `multitenancy`、§5 |
| 数据库 MySQL | §2、§11.1 |
| 本地磁盘对象存储 | §2、§5.3、§11.1 |
| **Skills 本地 FS 存储** | **§8.2 `skills.storage_path`、§11.1 `skills` volume** |
| docker-compose 一键起 | §11 |
| 全局日志 JSON 行 | §2、§14.13 |
| 系统内部使用，无公网暴露 | §3.1、§13 |

---

## 16. 待后续澄清事项（实施阶段仍可能出现的）

1. **分片上传**：v1 暂时不做分片（单文件上传足够小开发验证）。视频文件超大时再补分片，需多写 `tus.io` 或自实现。
2. **CELERY result backend 选型**：默认走 Redis；如果要保留历史任务结果可改 DB。
3. **AES-GCM 主密钥**：v1 用 env `MASTER_SECRET` 即可；如未来上 KMS 调整接口即可。
4. **`claude` CLI 安装方式**：Dockerfile 内 `npm install -g @anthropic-ai/claude-code` 或 bind mount。
5. **`/admin` 访问来源**：admin web 路由是 SPA 内的 `/admin/*` 还是独立子域名？v1 同源同前缀即可。
6. **错误国际化**：错误信息 v1 仅中文；admin 配置页面的 provider 列表、模型名仍英文 OK。
