# 影知 · API

FastAPI + SQLAlchemy 2（async）+ Alembic + Celery + Redis + MySQL。

本地启动见 [本地部署与开发](../docs/development.md)。产品说明见 [功能说明](../docs/features.md)，采集见 [采集说明](../docs/collection.md)。

```bash
# 仓库根目录
make middleware
make migrate
make api            # uvicorn :8000
make media-worker   # -Q media
make worker         # -Q studio
```

或在 `api/` 内：`uv sync` 之后 `uv run uvicorn app.main:app --reload --port 8000`。
