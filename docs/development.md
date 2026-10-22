# 开发环境

## 前置

- Python 3.12+（[uv](https://github.com/astral-sh/uv)）
- Node 18+（npm）
- Docker（跑 mysql / redis / qdrant）
- 系统级：`ffmpeg`；YouTube 抓取建议装 **Deno**（EJS challenge）

```bash
# Deno（可选，推荐）
curl -fsSL https://deno.land/install.sh | sh
export PATH="$HOME/.deno/bin:$PATH"
```

## 启动

```bash
cp .env.example .env
make middleware
make migrate
make api            # http://127.0.0.1:8000/docs
make web            # http://127.0.0.1:5173  （/api 代理到 8000）
make media-worker   # 抓取 / 字幕 / 向量索引
make worker         # Studio（需本机 Claude CLI）
```

健康检查：

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/health/ready
```

## 常用 make

| 命令 | 作用 |
|------|------|
| `make middleware` | 起中间件 |
| `make down` | 关中间件 |
| `make up` / `make down-all` | 全栈 Compose 起 / 停 |
| `make api` / `web` / `media-worker` / `worker` | 本地进程 |
| `make migrate` | alembic upgrade head |
| `make test` / `typecheck` / `build` | 测试与构建 |

完整列表：`make help`。

## 本地 vs Compose

| | 本地开发 | Compose 一键 |
|--|----------|--------------|
| 中间件 | `make middleware` | 含在 `docker compose up` |
| api / web / worker | 本机进程，热重载 | 容器；web 为 nginx 产物 |
| `.env` 主机名 | `127.0.0.1` | Compose `environment` 覆盖为服务名 |
| 存储路径 | `./storage`、`./skills` | 挂到 `/data/...` |

部署细节见 [deployment.md](deployment.md)。
