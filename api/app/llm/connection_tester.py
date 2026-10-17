"""Provider 连通性测试。

参考 open-notebook/open_notebook/ai/connection_tester.py 的设计：
- 用 `provider_registry.PROVIDERS` 自动确定测试方式。
- OpenAI-兼容：GET {base_url}/v1/models，最小调用。
- Anthropic：用 test_model 发一条短 prompt。
- Gemini：列模型。
- Whisper：复用 OpenAI 兼容。

返回：
{
    "ok": bool,
    "latency_ms": int,
    "provider": str,
    "message"?: str,
    "error"?: str,
}
"""
from __future__ import annotations

import time

import httpx

from app.llm.provider_registry import PROVIDERS, ProviderSpec


async def _test_openai_compat(spec: ProviderSpec, api_key: str, base_url: str) -> dict:
    started = time.monotonic()
    try:
        base = base_url.rstrip("/")
        url = f"{base}{spec.test_url_path}"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
            )
        elapsed = int((time.monotonic() - started) * 1000)
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            return {
                "ok": True,
                "latency_ms": elapsed,
                "provider": spec.name,
                "message": f"服务可达；可识别模型/条目数 = {len(data) if isinstance(data, list) else '?'}",
            }
        return {
            "ok": False,
            "latency_ms": elapsed,
            "provider": spec.name,
            "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "provider": spec.name,
            "error": f"{exc.__class__.__name__}: {exc}",
        }


async def _test_anthropic(spec: ProviderSpec, api_key: str, base_url: str) -> dict:
    started = time.monotonic()
    try:
        import httpx as _hx

        base = base_url.rstrip("/")
        url = f"{base}/v1/messages"
        # Anthropic: 用最小的 max_tokens 探测
        async with _hx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                url,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": spec.test_model or "claude-haiku-4-5-20251001",
                    "max_tokens": 8,
                    "messages": [{"role": "user", "content": "OK"}],
                },
            )
        elapsed = int((time.monotonic() - started) * 1000)
        if resp.status_code in (200, 201):
            return {
                "ok": True,
                "latency_ms": elapsed,
                "provider": spec.name,
                "message": f"模型 {spec.test_model} 可调用",
            }
        return {
            "ok": False,
            "latency_ms": elapsed,
            "provider": spec.name,
            "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
        }
    except Exception as exc:
        return {
            "ok": False,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "provider": spec.name,
            "error": f"{exc.__class__.__name__}: {exc}",
        }


async def _test_gemini(spec: ProviderSpec, api_key: str, base_url: str) -> dict:
    started = time.monotonic()
    try:
        base = base_url.rstrip("/")
        url = f"{base}/models?key={api_key}"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
        elapsed = int((time.monotonic() - started) * 1000)
        if resp.status_code == 200:
            data = resp.json().get("models", [])
            return {
                "ok": True,
                "latency_ms": elapsed,
                "provider": spec.name,
                "message": f"Gemini API 可达；可调用模型数 = {len(data)}",
            }
        return {
            "ok": False,
            "latency_ms": elapsed,
            "provider": spec.name,
            "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
        }
    except Exception as exc:
        return {
            "ok": False,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "provider": spec.name,
            "error": f"{exc.__class__.__name__}: {exc}",
        }


async def test_credential(
    provider: str,
    api_key: str,
    *,
    base_url: str | None = None,
) -> dict:
    """统一入口：根据 provider 分发到合适的测试方式。"""
    spec = PROVIDERS.get(provider)
    if spec is None:
        return {
            "ok": False,
            "latency_ms": 0,
            "provider": provider,
            "error": f"unknown provider: {provider}",
        }
    if not api_key:
        return {
            "ok": False,
            "latency_ms": 0,
            "provider": provider,
            "error": "缺少 api_key",
        }
    base = (base_url or spec.default_base_url or "").rstrip("/")
    if not base:
        return {
            "ok": False,
            "latency_ms": 0,
            "provider": provider,
            "error": "缺少 base_url，且 provider 没有 default_base_url",
        }

    if spec.name == "anthropic":
        return await _test_anthropic(spec, api_key, base)
    if spec.name == "gemini":
        return await _test_gemini(spec, api_key, base)
    # openai / minimax / whisper：OpenAI 兼容
    return await _test_openai_compat(spec, api_key, base)
