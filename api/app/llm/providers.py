"""LLM provider 实现。

Phase 3.5 重构后，make_provider 接收的是「provider name + base_url + api_key」，
不再用 LlmConfig row。模型名与 credential 一起由调用方传入。

v1 仅 minimax 走 Anthropic-兼容 SDK；其它 provider（openai / gemini）走各自的 SDK。
为简化代码量并避免依赖过多 anthropic/openai SDK 共存冲突，v1 暂时用
`provider name` 简单分发：minimax 走 anthropic SDK，openai 用 stub（Phase 6 后扩）。
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from anthropic import AsyncAnthropic

from app.llm.base import LlmProvider
from app.llm.usage import parse_usage


def _parse_params(params_json: dict | None) -> dict[str, Any]:
    if not params_json:
        return {}
    return {k: v for k, v in params_json.items() if isinstance(v, (int, float, str, bool))}


# anthropic SDK 1.15 起 messages.create/stream 不再接受 temperature、top_p。
# MiniMax 的兼容接口仍认这两个字段，有值时放到 extra_body 里发出去。
_SAMPLING_KEYS = ("temperature", "top_p")


def build_chat_messages(
    prompt: str, history: list[dict[str, str]] | None
) -> list[dict[str, str]]:
    """拼成 Anthropic 要求的 user/assistant 交替消息。当前问题放在最后。"""
    messages: list[dict[str, str]] = []
    for item in history or []:
        role = item.get("role")
        content = (item.get("content") or "").strip()
        if role not in ("user", "assistant") or not content:
            continue
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"] += "\n\n" + content
            continue
        messages.append({"role": role, "content": content})
    if messages and messages[0]["role"] != "user":
        messages = messages[1:]
    if messages and messages[-1]["role"] == "user":
        messages[-1]["content"] += "\n\n" + prompt
        return messages
    messages.append({"role": "user", "content": prompt})
    return messages


def _extra_body(kwargs: dict[str, Any]) -> dict[str, Any] | None:
    body = {
        key: kwargs[key]
        for key in _SAMPLING_KEYS
        if isinstance(kwargs.get(key), (int, float))
    }
    return body or None


def anthropic_base_url(base_url: str | None) -> str | None:
    """把后台保存的 OpenAI 兼容地址改成 Anthropic SDK 能用的 base。

    SDK 会在 base 后面再拼 `/v1/messages`。凭证里的 MiniMax 地址是
    `https://api.minimaxi.com/v1`（用来列模型），直接传进去会打到
    `…/v1/v1/messages`，网关回 `404 page not found`。
    MiniMax 的 Anthropic 兼容入口是同主机的 `/anthropic`。
    """
    if not base_url:
        return None
    raw = base_url.strip().rstrip("/")
    parsed = urlsplit(raw)
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/")
    if path == "/v1" or path.endswith("/v1"):
        path = path[: -len("/v1")]
    if "minimax" in host and path in ("", "/anthropic"):
        path = "/anthropic"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", "")).rstrip("/")


class AnthropicCompatProvider(LlmProvider):
    """走 Anthropic Messages API 的 provider（minimax、未来 anthropic）。"""

    def _client(self, base_url: str | None) -> AsyncAnthropic:
        return AsyncAnthropic(
            api_key=self.api_key,
            base_url=anthropic_base_url(base_url),
        )

    async def complete(self, prompt: str, *, system: str | None = None, **kwargs: Any) -> str:
        kwargs = {**_parse_params(self.params_json), **kwargs}
        client = self._client(self.base_url)
        resp = await client.messages.create(
            model=self.model_name,
            max_tokens=int(kwargs.get("max_tokens", 4096)),
            system=system or "",
            messages=[{"role": "user", "content": prompt}],
            extra_body=_extra_body(kwargs),
        )
        self.last_usage = parse_usage(getattr(resp, "usage", None)) or parse_usage(resp)
        parts = []
        for block in resp.content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return "\n".join(parts)

    async def stream_chat(
        self,
        prompt: str,
        *,
        system: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        kwargs = {**_parse_params(self.params_json), **kwargs}
        client = self._client(self.base_url)
        history = kwargs.get("history")
        self.last_usage = None
        async with client.messages.stream(
            model=self.model_name,
            max_tokens=int(kwargs.get("max_tokens", 4096)),
            system=system or "",
            messages=build_chat_messages(prompt, history if isinstance(history, list) else None),
            extra_body=_extra_body(kwargs),
        ) as stream:
            async for text in stream.text_stream:
                if text:
                    yield text
            final = None
            try:
                final = await stream.get_final_message()
            except Exception:
                final = None
            usage = parse_usage(final)
            if usage is None and final is not None:
                usage = parse_usage(getattr(final, "usage", None))
            self.last_usage = usage


class StubLlmProvider(LlmProvider):
    """未实装 provider 时的兜底。"""

    async def complete(self, prompt: str, *, system: str | None = None, **kwargs: Any) -> str:
        return (
            "[stub LLM] 已收到长度 " + str(len(prompt)) + " 的 prompt。"
            "请在 admin 后台为此 role 设置默认模型（已有 LLM Provider 绑定）。"
        )

    async def stream_chat(
        self, prompt: str, *, system: str | None = None, **kwargs: Any
    ) -> AsyncIterator[str]:
        text = await self.complete(prompt, system=system)
        for chunk in (text[i : i + 32] for i in range(0, len(text), 32)):
            yield chunk


def make_provider(
    *,
    provider_name: str,
    api_key: str,
    base_url: str | None,
    model_name: str,
    params_json: dict | None = None,
) -> LlmProvider:
    """统一工厂：依据 provider 名称选具体实现。

    v1：minimax 走 Anthropic 兼容；openai/gemini 暂时走 stub（Phase 7 实装 streaming 真实调用）。
    """
    config_like = {
        "provider": provider_name,
        "base_url": base_url,
        "model_name": model_name,
        "params_json": params_json or {},
    }

    if provider_name in ("minimax", "anthropic"):
        return AnthropicCompatProvider(config_like, api_key)
    return StubLlmProvider(config_like, api_key)
