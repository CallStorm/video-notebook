# Makefile — 给开发时方便用。`make` 看可用命令。

# 装载 .env（如有）；uvicorn / vite 等会自动读。
SHELL := /usr/bin/env bash

.PHONY: help middleware up down api web worker media-worker migrate typecheck test build clean

help:
	@echo "常用命令："
	@echo "  make middleware       # 启动 mysql + redis 容器"
	@echo "  make down             # 关掉容器（含数据卷慎用 v）"
	@echo "  make api              # 本地起 api (uvicorn --reload)"
	@echo "  make web              # 本地起 web (vite dev)"
	@echo "  make worker           # 本地起 studio celery worker"
	@echo "  make media-worker     # 本地起 media celery worker（抓取+字幕）"
	@echo "  make migrate          # alembic upgrade head"
	@echo "  make migration m=...  # 生成 alembic revision"
	@echo "  make test             # api pytest"
	@echo "  make typecheck        # api typecheck + web typecheck"
	@echo "  make build            # web 生产构建"
	@echo "  make clean            # 清理 build / cache（不动数据卷）"

middleware:
	docker compose -f compose.middleware.yml up -d

down:
	docker compose -f compose.middleware.yml down

api:
	cd api && uv run uvicorn app.main:app --reload --port 8000

web:
	cd web && npm run dev

worker:
	cd api && uv run celery -A app.studio.worker:celery_app worker -Q studio -c 2

media-worker:
	cd api && uv run celery -A app.media.worker:celery_app worker -Q media -c 4 -n media@%h

migrate:
	cd api && uv run alembic upgrade head

migration:
	cd api && uv run alembic revision --autogenerate -m "$(m)"

test:
	cd api && uv run pytest -q

typecheck:
	cd api && uv run ruff check app/ tests/
	cd web && npm run typecheck

build:
	cd web && npm run build

clean:
	rm -rf web/dist api/.pytest_cache api/.ruff_cache api/.coverage web/node_modules/.cache
