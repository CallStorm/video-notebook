# video-notebook · API

FastAPI + SQLAlchemy 2 (async) + Alembic + Celery + Redis + MySQL。

产品与本地启动见仓库根目录 [README](../README.md) 与 [docs/development.md](../docs/development.md)。

```bash
# 仓库根目录
make middleware
make migrate
make api            # uvicorn :8000
make media-worker   # -Q media
make worker         # -Q studio
```

或在 `api/` 内：`uv sync` 后 `uv run uvicorn app.main:app --reload --port 8000`。
