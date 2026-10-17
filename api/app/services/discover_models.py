"""Provider 模型发现：调 provider /v1/models 拿候选。

参考 open-notebook/open_notebook/ai/model_discovery.py + open_notebook/ai/connection_tester.py 的
做法。我们做精简版：所有 provider 都走 OpenAI 兼容 GET /v1/models 模式。

⚠️ 路径拼接：用 provider_registry 的 `test_url_path` 字段（默认 `/models`），
**不要**自己拼 `/v1/models` —— 多数 provider 的 `default_base_url` 已经以 `/v1`
结尾，自己拼会得到 `.../v1/v1/models` → 404。
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from app.llm.provider_registry import PROVIDERS
from app.models.credential import Credential


@dataclass
class DiscoveryResult:
    items: list[dict]  # [{"name": str, "description": str|None}, ...]
    error: str | None = None
    latency_ms: int = 0


def _extract_model_id(entry: dict) -> str | None:
    """从 OpenAI-兼容 /v1/models 响应里取模型 id。

    OpenAI、DeepSeek 等标准格式用 "id"。minimax 等有时把模型名放在 "model" 或 "name"
    字段，size / object / created 等元数据也可能喧宾夺主。容错取第一个看起来像字符串
    id 的字段。
    """
    for key in ("id", "model", "name"):
        val = entry.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return None


async def discover_models(credential: Credential) -> DiscoveryResult:
    """对一条凭证做发现：调 provider 兼容 /v1/models 解析 data[]."""
    spec = PROVIDERS.get(credential.provider)
    if spec is None:
        return DiscoveryResult(items=[], error=f"unknown provider: {credential.provider}")
    base = (credential.base_url or spec.default_base_url or "").rstrip("/")
    if not base:
        return DiscoveryResult(items=[], error="缺少 base_url")

    # 复用 registry 的 test_url_path（默认 /models；base_url 已含 /v1）
    url = f"{base}{spec.test_url_path}"
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {credential.get_api_key()}"},
            )
    except Exception as exc:  # noqa: BLE001
        return DiscoveryResult(
            items=[],
            error=f"{exc.__class__.__name__}: {exc}",
            latency_ms=int((time.monotonic() - started) * 1000),
        )

    elapsed = int((time.monotonic() - started) * 1000)
    if resp.status_code != 200:
        return DiscoveryResult(
            items=[],
            error=f"HTTP {resp.status_code}: {resp.text[:200]}",
            latency_ms=elapsed,
        )

    try:
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        return DiscoveryResult(items=[], error=f"无法解析响应: {exc}", latency_ms=elapsed)

    # OpenAI 标准 `data: [...]`；minimax 等有时顶层就是 `[...]`；个别是 `models: [...]`
    items_field: list = []
    if isinstance(data, list):
        items_field = data
    elif isinstance(data, dict):
        for key in ("data", "models", "items", "results"):
            v = data.get(key)
            if isinstance(v, list):
                items_field = v
                break
    if not items_field:
        return DiscoveryResult(items=[], error="响应中找不到模型列表（试了 data/models/items）", latency_ms=elapsed)

    items: list[dict] = []
    for entry in items_field:
        if not isinstance(entry, dict):
            # minimax 偶尔返回裸字符串数组
            if isinstance(entry, str) and entry.strip():
                items.append({"name": entry, "description": None})
            continue
        name = _extract_model_id(entry)
        if not name:
            continue
        items.append(
            {
                "name": name,
                "provider": credential.provider,
                "description": entry.get("description") or None,
            }
        )

    return DiscoveryResult(items=items, error=None, latency_ms=elapsed)
