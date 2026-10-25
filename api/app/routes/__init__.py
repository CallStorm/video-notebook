"""HTTP 路由聚合。

Phase 3.5：删 LLM/ASR config 端点，改用 credentials / models / default-models。
"""
from __future__ import annotations

from fastapi import APIRouter

from app.routes import (
    admin,
    admin_agents,
    admin_claude,
    admin_credentials,
    admin_default_models,
    admin_fetch_network,
    admin_fetch_settings,
    admin_subtitle_slice_settings,
    admin_overview_settings,
    admin_cover_settings,
    admin_chat_settings,
    admin_vector_settings,
    admin_observability,
    admin_stats,
    admin_models,
    admin_skills,
    admin_studio,
    auth,
    chat,
    collections,
    covers,
    health,
    icons,
    notebooks,
    providers,
    search,
    sources,
    studio,
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
api_router.include_router(admin_skills.router)
api_router.include_router(admin_agents.router)
api_router.include_router(admin_claude.router)
api_router.include_router(admin_fetch_network.router)
api_router.include_router(admin_fetch_settings.router)
api_router.include_router(admin_subtitle_slice_settings.router)
api_router.include_router(admin_overview_settings.router)
api_router.include_router(admin_cover_settings.router)
api_router.include_router(admin_chat_settings.router)
api_router.include_router(admin_vector_settings.router)
api_router.include_router(admin_observability.router)
api_router.include_router(admin_stats.router)
api_router.include_router(admin_studio.router)
# 公共 provider 元数据
api_router.include_router(providers.router)
# Phase 4：notebook / source
api_router.include_router(notebooks.router)
api_router.include_router(collections.router)
api_router.include_router(icons.router)
api_router.include_router(covers.router)
api_router.include_router(sources.router)
api_router.include_router(search.router)
api_router.include_router(chat.router)
api_router.include_router(studio.router)

# /api/storage/{key} 视频代理（签发 token 校验后流式回写）
from app.routes import storage_proxy  # noqa: E402

api_router.include_router(storage_proxy.router)
