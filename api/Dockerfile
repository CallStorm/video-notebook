# syntax=docker/dockerfile:1.7

# ── build stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/usr/local \
    DENO_INSTALL=/usr/local \
    PATH="/usr/local/bin:${PATH}"

# uv: 静态二进制，独立于系统包管理。
COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /uvx /usr/local/bin/

WORKDIR /app

# media-worker 需要 ffmpeg；YouTube EJS challenge 需要 Deno（装失败不阻断构建）。
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates curl unzip \
    && rm -rf /var/lib/apt/lists/* \
    && (curl -fsSL https://deno.land/install.sh | sh) || echo "WARN: Deno install failed; YouTube JS challenge may need host Deno"

# 依赖层缓存：只改 pyproject/uv.lock 时不重新装包。
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-install-project --no-dev || true

# 项目代码
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

RUN uv sync --no-dev

# 暴露端口（仅文档意义，实际由 docker-compose 决定）
EXPOSE 8000

# 默认入口由 docker-compose 覆盖；这里给一个合理的兜底
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
