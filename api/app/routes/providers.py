"""公共 /api/providers 端点。前端下拉、选择项等都用这里。

不需要鉴权：只暴露 provider 元数据（不含密文）。
"""
from __future__ import annotations

from fastapi import APIRouter

from app.llm.provider_registry import PROVIDERS
from app.schemas.provider import ProviderInfo

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("", response_model=list[ProviderInfo])
async def list_providers() -> list[ProviderInfo]:
    """列出所有支持的 provider。返回顺序与 registry 声明顺序一致。"""
    return [
        ProviderInfo(
            name=spec.name,
            display_name=spec.display_name,
            modalities=list(spec.modalities),
            default_base_url=spec.default_base_url,
            test_model=spec.test_model,
            docs_url=spec.docs_url,
            anthropic_compat=spec.anthropic_compat,
        )
        for spec in PROVIDERS.values()
    ]
