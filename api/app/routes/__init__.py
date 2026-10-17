"""HTTP 路由聚合。

Phase 3.5：删 LLM/ASR config 端点，改用 credentials / models / default-models。
"""
from __future__ import annotations

from fastapi import APIRouter

from app.routes import (
    admin,
    admin_credentials,
    admin_default_models,
    admin_models,
    auth,
    chat,
    health,
    notebooks,
    providers,
    sources,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(admin.router)
# Phase 3.5：替换 admin_configs（已删）
api_router.include_router(admin_credentials.router)
api_router.include_router(admin_models.router)
api_router.include_router(admin_default_models.router)
# 公共 provider 元数据
api_router.include_router(providers.router)
# Phase 4：notebook / source
api_router.include_router(notebooks.router)
api_router.include_router(sources.router)
api_router.include_router(chat.router)

# /api/storage/{key} 视频代理（签发 token 校验后流式回写）
from app.routes import storage_proxy  # noqa: E402

api_router.include_router(storage_proxy.router)
