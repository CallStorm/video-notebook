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

`docker compose up`（在仓库根）会一起起 api、worker、web、mysql、redis。
