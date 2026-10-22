# 部署

## 一键 Compose

```bash
cp .env.example .env    # 已有勿覆盖；务必改 JWT / MYSQL / SEED 密码
# 可选：对照 .env.docker.example 了解 Compose 内会覆盖哪些主机名
docker compose up -d --build
# 或：make up
```

| 入口 | URL |
|------|-----|
| Web | http://127.0.0.1:8080 |
| API / OpenAPI | http://127.0.0.1:8000/docs |
| 经 Web 反代的 API | http://127.0.0.1:8080/api/... |

停止（保留数据卷）：

```bash
docker compose down
# 或：make down-all
```

## 拓扑

`docker-compose.yml` **include** `compose.middleware.yml`，再起：

| 服务 | 说明 |
|------|------|
| mysql / redis / qdrant | 中间件；端口绑 `127.0.0.1` |
| api | 启动时 `alembic upgrade head`，再 uvicorn |
| media-worker | 同 api 镜像，`-Q media` |
| studio-worker | 同 api 镜像，`-Q studio` |
| web | nginx 托管前端，反代 `/api/` → api |

卷：`./storage` → `/data/video-notebook`，`./skills` → `/data/skills`。

## 环境变量

- 密钥、SEED、LLM/ASR 等：写在根目录 `.env`（`env_file`）。
- Compose **强制覆盖**容器内连接：
  - `MYSQL_HOST=mysql`
  - `REDIS_URL=redis://redis:6379/0`
  - `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` → redis db1 / db2
  - `STORAGE_ROOT=/data/video-notebook`，`SKILLS_ROOT=/data/skills`
- 参考说明：`.env.docker.example`。

## Qdrant 地址

向量库 URL 多存在**后台「向量配置」**，默认常为 `http://127.0.0.1:6333`。  
全栈都在 Compose 网络里时，请改为：

```text
http://qdrant:6333
```

本机浏览器访问 Qdrant Dashboard 仍可用 `http://127.0.0.1:6333`。

## 升级

```bash
git pull
docker compose up -d --build
# api 容器启动时会自动 alembic upgrade head
```

## 已知限制

1. **Claude CLI**：镜像默认不内置。Studio 任务需本机安装 `claude` 并挂进容器，或改用本地 `make worker`。
2. **Deno**：api 镜像构建时会尝试安装；失败则 YouTube JS challenge 可能失败，可在宿主机装 Deno 或修镜像后再 build。
3. **Makefile** 依赖 bash；Windows 可用 Git Bash，或直接敲 `docker compose ...`。
4. 中间件端口仅本机回环；Web `8080`、API `8000` 亦绑 `127.0.0.1`。

## 仅中间件（本地进程开发）

```bash
make middleware   # 等价 docker compose -f compose.middleware.yml up -d
```

然后本机 `make api` / `web` / `media-worker` / `worker`。见 [development.md](development.md)。
