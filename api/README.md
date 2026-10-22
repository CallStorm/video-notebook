# video-notebook · API

FastAPI + SQLAlchemy 2 (async) + Alembic + Celery + Redis + MySQL.

详细设计与需求在仓库根 `docs/`。

## 本地开发

```bash
# 安装依赖（使用 uv）
cd api
uv sync
uv run uvicorn app.main:app --reload
```

URL 抓取与字幕在独立 Celery worker 里跑（不要只起 API）：

```bash
# 仓库根
make media-worker
# 或：cd api && uv run celery -A app.media.worker:celery_app worker -Q media -c 8
```

Studio 任务仍用 `make worker`（队列 `studio`）。

测试：

```bash
uv run pytest
```

迁移：

```bash
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
```

## 容器化

仓库根目录 `docker compose up -d --build`（或 `make up`）会一起起  
mysql / redis / qdrant / api / media-worker / studio-worker / web。  
说明见 [`docs/deployment.md`](../docs/deployment.md)。
