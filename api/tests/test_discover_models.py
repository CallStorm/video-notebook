"""discover_models 服务测试：URL 拼接、响应解析、错误处理。"""
from __future__ import annotations

import time
from types import ModuleType
from unittest.mock import AsyncMock

import pytest

from app.models.credential import Credential
from app.services.discover_models import discover_models


def _make_cred(provider: str, base_url: str | None, key: str = "sk-test") -> Credential:
    cred = Credential(
        name="cred",
        provider=provider,
        modalities_json=["language", "text_to_speech"],
        base_url=base_url,
        is_builtin=False,
    )
    cred.set_api_key(key)
    return cred


def _patch_httpx(monkeypatch, fake_response_factory) -> None:
    """替换 services.discover_models 里的 httpx。"""

    class _FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def get(self, url, **kwargs):
            return fake_response_factory(url)

    fake_mod = ModuleType("httpx_fake")
    fake_mod.AsyncClient = _FakeClient
    monkeypatch.setattr("app.services.discover_models.httpx", fake_mod)


# ─── URL 拼接 ────────────────────────────────────────────────
async def test_minimax_user_url_does_not_double_v1(monkeypatch):
    """minimax base_url='api.minimaxi.com/v1' 时，URL 必须是 api.minimaxi.com/v1/models，
    不是 /v1/v1/models。"""
    captured: dict = {}

    def factory(url):
        captured["url"] = url
        resp = AsyncMock()
        resp.status_code = 200
        resp.json = lambda: {"data": []}
        return resp

    _patch_httpx(monkeypatch, factory)
    cred = _make_cred("minimax", "https://api.minimaxi.com/v1")
    await discover_models(cred)
    assert captured["url"] == "https://api.minimaxi.com/v1/models", captured


async def test_openai_default_url(monkeypatch):
    captured: dict = {}

    def factory(url):
        captured["url"] = url
        resp = AsyncMock()
        resp.status_code = 200
        resp.json = lambda: {"data": []}
        return resp

    _patch_httpx(monkeypatch, factory)
    cred = _make_cred("openai", None)  # 用 default
    await discover_models(cred)
    assert captured["url"] == "https://api.openai.com/v1/models", captured


# ─── 响应解析 ────────────────────────────────────────────────
async def test_parses_openai_standard_data_array(monkeypatch):
    def factory(url):
        resp = AsyncMock()
        resp.status_code = 200
        resp.json = lambda: {
            "data": [
                {"id": "gpt-4o"},
                {"id": "gpt-3.5-turbo", "description": "fast"},
            ]
        }
        return resp

    _patch_httpx(monkeypatch, factory)
    cred = _make_cred("openai", "https://api.openai.com/v1")
    result = await discover_models(cred)
    assert result.error is None
    assert [it["name"] for it in result.items] == ["gpt-4o", "gpt-3.5-turbo"]
    assert result.items[1]["description"] == "fast"


async def test_parses_minimax_model_field(monkeypatch):
    """minimax 用 'model' 字段而不是 'id'。"""
    def factory(url):
        resp = AsyncMock()
        resp.status_code = 200
        resp.json = lambda: {
            "data": [
                {"model": "MiniMax-Text-01"},
                {"model": "MiniMax-M2"},
            ]
        }
        return resp

    _patch_httpx(monkeypatch, factory)
    cred = _make_cred("minimax", "https://api.minimaxi.com/v1")
    result = await discover_models(cred)
    assert result.error is None
    assert [it["name"] for it in result.items] == ["MiniMax-Text-01", "MiniMax-M2"]


async def test_parses_minimax_top_level_array(monkeypatch):
    """minimax 等偶尔把 list 放在顶层而不是 data 里。"""
    def factory(url):
        resp = AsyncMock()
        resp.status_code = 200
        resp.json = lambda: ["model-a", "model-b"]
        return resp

    _patch_httpx(monkeypatch, factory)
    cred = _make_cred("minimax", "https://api.minimaxi.com/v1")
    result = await discover_models(cred)
    assert result.error is None
    assert [it["name"] for it in result.items] == ["model-a", "model-b"]


async def test_parses_models_field(monkeypatch):
    """部分 provider 用 'models' 字段。"""
    def factory(url):
        resp = AsyncMock()
        resp.status_code = 200
        resp.json = lambda: {
            "models": [{"id": "deepseek-chat"}]
        }
        return resp

    _patch_httpx(monkeypatch, factory)
    cred = _make_cred("deepseek", "https://api.deepseek.com/v1")
    result = await discover_models(cred)
    assert [it["name"] for it in result.items] == ["deepseek-chat"]


async def test_handles_401(monkeypatch):
    def factory(url):
        resp = AsyncMock()
        resp.status_code = 401
        resp.text = "Unauthorized"
        return resp

    _patch_httpx(monkeypatch, factory)
    cred = _make_cred("minimax", "https://api.minimaxi.com/v1")
    result = await discover_models(cred)
    assert result.error is not None
    assert "401" in result.error
    assert result.items == []


async def test_handles_network_error(monkeypatch):
    def factory(url):
        raise ConnectionError("boom")

    _patch_httpx(monkeypatch, factory)
    cred = _make_cred("minimax", "https://api.minimaxi.com/v1")
    result = await discover_models(cred)
    assert "boom" in (result.error or "")


async def test_missing_base_url(monkeypatch):
    """v1 还没加 base_url 时，default_base_url 是 None，应该报错。"""
    # 直接构造一个 provider 让 default_base_url 为 None
    from app.llm.provider_registry import PROVIDERS, ProviderSpec

    original = PROVIDERS.get("minimax")
    if original is None:
        pytest.skip("minimax not in registry")
    try:
        # monkeypatch PROVIDERS 让 minimax default_base_url = None
        from app.services import discover_models as dm_mod

        new_spec = ProviderSpec(
            name="minimax",
            display_name=original.display_name,
            modalities=original.modalities,
            default_base_url=None,
            test_model=original.test_model,
            docs_url=original.docs_url,
            anthropic_compat=original.anthropic_compat,
        )
        dict(dm_mod.PROVIDERS.__dict__) if False else None
        # 直接在 module 命名空间里覆盖
        dm_mod.PROVIDERS = {**dm_mod.PROVIDERS, "minimax": new_spec}
        cred = _make_cred("minimax", None)
        result = await dm_mod.discover_models(cred)
        assert "缺少 base_url" in (result.error or "")
    finally:
        # 还原（直接覆盖整个 dict）
        if original is not None:
            from app.llm import provider_registry as pr_mod

            dm_mod.PROVIDERS = pr_mod.PROVIDERS


# 简单时间 sanity check（防止路径写错导致请求打到错地方）
async def test_latency_is_recorded(monkeypatch):
    def factory(url):
        resp = AsyncMock()
        resp.status_code = 200
        resp.json = lambda: {"data": []}
        return resp

    _patch_httpx(monkeypatch, factory)
    cred = _make_cred("minimax", "https://api.minimaxi.com/v1")
    started = time.monotonic()
    result = await discover_models(cred)
    assert result.latency_ms >= 0
    assert time.monotonic() - started < 5
