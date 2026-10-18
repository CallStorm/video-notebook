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
- 系统级：`ffmpeg`、**Deno**（推荐，YouTube JS challenge）或 Node
- Python 依赖含 `yt-dlp` / `yt-dlp-ejs`（见 `api/`）

### 启动

```bash
# 0. 准备 .env
cp .env.example .env

# 1. 启动中间件
make middleware

# 2. 启动 api（另一个终端；YouTube 抓取建议带上 Deno）
export PATH="$HOME/.deno/bin:$PATH"
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

## 功能现状（摘要）

| 能力 | 状态 | 说明 |
|---|---|---|
| 鉴权 / 笔记本 / 本地上传 | ✅ | multipart 上传 → 存储 → 字幕流水线 |
| URL 抓取（YouTube + 直链） | ✅ | yt-dlp；直链 `.mp4` 等走 httpx |
| 字幕（内嵌 / 平台 / ASR） | ✅ | 失败可「重新生成」 |
| 聊天 + Studio（思维导图 / PPT） | ✅ | Skills / Agents 管理后台 |
| Collections（集合） | ✅ | 列表 / 详情 / 加入集合 |
| B 站 / 抖音 URL | ⏳ 计划中 | 仍走 yt-dlp，按平台补 cookie / 客户端参数 |
| 全网 / 平台搜索 → 入库分析 | ⏳ 计划中 | 见下方路线图 |

## 实施进度（相对设计 §14）

| Phase | 内容 | 状态 |
|---|---|---|
| 1 | API / Web 骨架 + 中间件 | ✅ |
| 2 | 鉴权与账号 | ✅ |
| 3 | 模型配置（LLM / ASR） | ✅ |
| 4 | 笔记本 + 来源 + 上传 | ✅ |
| 5 | URL 抓取 + 字幕链 | ✅（YouTube / 直链；B 站抖音待加强） |
| 6 | ASR 流水线 | ✅ |
| 7 | 聊天 + SSE | ✅ |
| 8–11 | Skills / Agents / Studio | ✅ |
| 12 | Discover + Collections | 部分（Collections ✅；Discover ⏳） |
| 13 | 打磨 | 进行中 |
| — | 搜索导入 + 多平台 | ⏳ 路线图 |

## URL 抓取

### 已支持
- **直链媒体**（`.mp4` / `.webm` / `.mkv` / `.mov` 等）：httpx 下载
- **YouTube**：yt-dlp + Deno（EJS）解 challenge；带 cookie 时使用 `default,web_embedded` 客户端
- 失败来源可在卡片菜单「重新抓取」

### Cookie（YouTube 等常需要）

优先用 **Netscape 格式 cookie 文件**（避免 macOS 钥匙串卡住）：

```bash
# .env（仓库根目录）
YTDLP_COOKIES_FILE=/absolute/path/to/youtube-cookies.txt
# YTDLP_COOKIES_FROM_BROWSER=chrome   # 易卡钥匙串，不推荐作默认
```

导出建议：Chrome 登录 YouTube → 扩展选 **Netscape** → 保存到上述路径。  
有效 cookie 应包含 `LOGIN_INFO`、`SID`、`SAPISID` 等；只有 `VISITOR_*` 不够。

Deno（YouTube JS challenge）：

```bash
curl -fsSL https://deno.land/install.sh | sh
export PATH="$HOME/.deno/bin:$PATH"
```

改 `.env` 后需**重启 API**（settings 有缓存）。

### 概览失败说明
概览走当前默认 LLM。若返回类似 `input new_sensitive` / 内容安全错误，是模型侧审核拦截，不是抓取失败；可换模型或换视频后再「重新生成」。

## 路线图

### 1. 多平台 URL：B 站、抖音
- 同一套 `sources/fetch` + yt-dlp；按域名选用 extractor / cookie
- B 站：支持 `bilibili.com` / `b23.tv`；可选 `SESSDATA` 等 cookie
- 抖音：支持分享链 / `v.douyin.com`；处理短链跳转与风控（可能需 cookie 或专用参数）
- UI：添加来源时提示「已支持平台」与 cookie 指引

### 2. 搜索 → 选片 → 分析
目标闭环：**搜索发现视频 → 一键加入笔记本 → 自动抓取 / 字幕 / 概览 / 可聊可 Studio**。

建议分期：

| 阶段 | 内容 |
|---|---|
| A. 站内搜索 | 笔记本 / 来源 / 集合按标题、描述、字幕关键词检索 |
| B. 平台搜索导入 | 对接 YouTube / B 站（及后续抖音）搜索 API 或 yt-dlp 搜索；结果列表勾选后 `fetch` 入库 |
| C. 分析编排 | 入库后自动跑字幕 → 概览 →（可选）推荐 Studio 任务；搜索页展示「分析中 / 就绪」状态 |

原则：搜索只负责发现与入队；分析复用现有抓取与字幕流水线，不另起一套处理逻辑。

## 常用命令

```bash
make middleware   # mysql + redis
make api          # FastAPI :8000
make web          # Vite :5173
cd api && uv run pytest -q --no-cov
cd web && npm run typecheck
```
