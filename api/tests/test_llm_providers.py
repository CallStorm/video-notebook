"""Anthropic 兼容调用不要把 SDK 已删除的参数直接传进去。"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.llm.providers import anthropic_base_url, make_provider


class _Block:
    text = "概览正文"


class _Resp:
    content = [_Block()]


class _Messages:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return _Resp()


class _Client:
    def __init__(self) -> None:
        self.messages = _Messages()


def test_minimax_openai_base_maps_to_anthropic_endpoint():
    assert anthropic_base_url("https://api.minimaxi.com/v1") == "https://api.minimaxi.com/anthropic"
    assert anthropic_base_url("https://api.minimax.io/v1/") == "https://api.minimax.io/anthropic"
    assert anthropic_base_url("https://api.minimaxi.com/anthropic") == "https://api.minimaxi.com/anthropic"
    assert anthropic_base_url("https://api.anthropic.com") == "https://api.anthropic.com"
    assert anthropic_base_url("https://api.anthropic.com/v1") == "https://api.anthropic.com"
    assert anthropic_base_url(None) is None


@pytest.mark.asyncio
async def test_complete_omits_temperature_when_unset():
    client = _Client()
    with patch("app.llm.providers.AsyncAnthropic", return_value=client):
        provider = make_provider(
            provider_name="minimax",
            api_key="sk-test",
            base_url="https://api.minimaxi.com/v1",
            model_name="MiniMax-M3",
        )
        text = await provider.complete("写概览", system="只输出正文", max_tokens=800)

    assert text == "概览正文"
    assert "temperature" not in client.messages.calls[0]
    assert client.messages.calls[0]["extra_body"] is None


@pytest.mark.asyncio
async def test_complete_sends_temperature_in_extra_body():
    client = _Client()
    with patch("app.llm.providers.AsyncAnthropic", return_value=client):
        provider = make_provider(
            provider_name="minimax",
            api_key="sk-test",
            base_url="https://api.minimaxi.com/v1",
            model_name="MiniMax-M3",
            params_json={"temperature": 0.2},
        )
        await provider.complete("写概览")

    assert "temperature" not in client.messages.calls[0]
    assert client.messages.calls[0]["extra_body"] == {"temperature": 0.2}


def test_anthropic_requires_stream_threshold():
    from app.llm.providers import anthropic_requires_stream

    assert anthropic_requires_stream(800) is False
    assert anthropic_requires_stream(21333) is False
    assert anthropic_requires_stream(21334) is True
    assert anthropic_requires_stream(200000) is True
    # Opus model-specific non-streaming cap
    assert anthropic_requires_stream(9000, "claude-opus-4-20250514") is True
    assert anthropic_requires_stream(4096, "claude-opus-4-20250514") is False


class _StreamCM:
    def __init__(self, chunks=("流式", "底稿")):
        self._chunks = chunks
        self.entered = False

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, *args):
        return False

    @property
    def text_stream(self):
        async def _gen():
            for c in self._chunks:
                yield c
        return _gen()

    async def get_final_message(self):
        return None


class _StreamMessages(_Messages):
    def __init__(self):
        super().__init__()
        self.stream_calls: list[dict] = []
        self._cm = _StreamCM()

    def stream(self, **kwargs):
        self.stream_calls.append(kwargs)
        return self._cm


class _StreamClient:
    def __init__(self):
        self.messages = _StreamMessages()


@pytest.mark.asyncio
async def test_complete_uses_stream_for_large_max_tokens():
    client = _StreamClient()
    with patch("app.llm.providers.AsyncAnthropic", return_value=client):
        provider = make_provider(
            provider_name="minimax",
            api_key="sk-test",
            base_url="https://api.minimaxi.com/v1",
            model_name="MiniMax-M3",
        )
        text = await provider.complete("写底稿", system="只输出 JSON", max_tokens=200000)

    assert text == "流式底稿"
    assert client.messages.calls == []
    assert len(client.messages.stream_calls) == 1
    assert client.messages.stream_calls[0]["max_tokens"] == 200000
