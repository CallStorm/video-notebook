"""OpenAI Chat Completions 兼容客户端。

Ollama、LM Studio、vLLM、llama.cpp server，以及 OpenAI / DeepSeek 官方接口，
都走 `{base}/chat/completions`。根地址自动补 `/v1`，显式填写的 API 前缀原样保留。

API Key 可空：本地服务通常不校验；有值时才带 `Authorization: Bearer`。
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.llm.base import LlmError, LlmProvider
from app.llm.provider_registry import get_provider
from app.llm.usage import parse_usage

_DEFAULT_READ_TIMEOUT = 900.0
_STRIP_SUFFIXES = (
    "/chat/completions",
    "/completions",
    "/embeddings",
    "/models",
)


def openai_compat_base_url(base_url: str | None) -> str:
    """仅为根地址补 /v1，保留网关自定义的版本与路径。"""
    raw = (base_url or "").strip()
    if not raw:
        raise LlmError("缺少 base_url")
    if "://" not in raw:
        raw = "http://" + raw
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise LlmError("Base URL 须为 HTTP(S) 地址，不包含凭据、查询参数或片段")
    path = parsed.path.rstrip("/")
    lowered = path.lower()
    for suffix in _STRIP_SUFFIXES:
        if lowered.endswith(suffix):
            path = path[: -len(suffix)].rstrip("/")
            break
    if not path:
        path = "/v1"
    scheme = parsed.scheme or "http"
    return urlunsplit((scheme, parsed.netloc, path, parsed.query, "")).rstrip("/")


def openai_chat_completions_url(base_url: str | None) -> str:
    return f"{openai_compat_base_url(base_url)}/chat/completions"


def openai_auth_headers(api_key: str | None, *, json_body: bool = False) -> dict[str, str]:
    """无 key 时不发 Authorization，避免本地服务拒绝空 Bearer。"""
    headers: dict[str, str] = {}
    if json_body:
        headers["Content-Type"] = "application/json"
    key = (api_key or "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


def _error_message(payload: Any, fallback: str) -> str:
    if isinstance(payload, dict):
        err = payload.get("error")
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])[:500]
        if isinstance(err, str) and err.strip():
            return err.strip()[:500]
    text = (fallback or "").strip()
    return text[:500] or "未知错误"


def _read_timeout(merged: dict[str, Any]) -> float:
    raw = merged.get("timeout_seconds")
    if isinstance(raw, (int, float)) and not isinstance(raw, bool) and raw > 0:
        return float(raw)
    return _DEFAULT_READ_TIMEOUT


def _max_tokens(merged: dict[str, Any]) -> int:
    raw = merged.get("max_tokens", 4096)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 4096
    return value if value > 0 else 4096


def _sampling(merged: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {}
    for key in ("temperature", "top_p", "presence_penalty", "frequency_penalty"):
        value = merged.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            body[key] = value
    return body


class OpenAICompatProvider(LlmProvider):
    """POST /v1/chat/completions，覆盖非流式 complete 与 SSE stream_chat。"""

    def __init__(self, config_like: dict[str, Any], api_key: str, **kwargs: Any) -> None:
        super().__init__(config_like, api_key, **kwargs)
        if not (self.base_url or "").strip():
            spec = get_provider(self.provider_name)
            if spec is not None and spec.default_base_url:
                self.base_url = spec.default_base_url

    def _merged(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        params = self.params_json or {}
        # bool 是 int 的子类；凭证里的开关不进请求体，只留字符串和数值。
        parsed = {
            key: value
            for key, value in params.items()
            if isinstance(value, str) or (isinstance(value, (int, float)) and not isinstance(value, bool))
        }
        return {**parsed, **kwargs}

    def _messages(self, prompt: str, system: str | None, history: Any) -> list[dict[str, str]]:
        from app.llm.providers import build_chat_messages

        messages: list[dict[str, str]] = []
        if system and system.strip():
            messages.append({"role": "system", "content": system})
        prior = history if isinstance(history, list) else None
        messages.extend(build_chat_messages(prompt, prior))
        return messages

    def _payload(self, prompt: str, system: str | None, merged: dict[str, Any], *, stream: bool) -> dict[str, Any]:
        if not (self.model_name or "").strip():
            raise LlmError("缺少模型名")
        body: dict[str, Any] = {
            "model": self.model_name,
            "messages": self._messages(prompt, system, merged.get("history")),
            ("max_completion_tokens" if self.provider_name == "openai" else "max_tokens"): _max_tokens(merged),
            "stream": stream,
        }
        if stream and self.provider_name in {"openai", "deepseek", "ollama"}:
            body["stream_options"] = {"include_usage": True}
        body.update(_sampling(merged))
        return body

    def _timeout(self, merged: dict[str, Any]) -> httpx.Timeout:
        return httpx.Timeout(connect=15.0, read=_read_timeout(merged), write=60.0, pool=15.0)

    async def complete(self, prompt: str, *, system: str | None = None, **kwargs: Any) -> str:
        self.last_usage = None
        merged = self._merged(kwargs)
        url = openai_chat_completions_url(self.base_url)
        payload = self._payload(prompt, system, merged, stream=False)
        try:
            async with httpx.AsyncClient(timeout=self._timeout(merged)) as client:
                resp = await client.post(
                    url,
                    headers=openai_auth_headers(self.api_key, json_body=True),
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise LlmError(f"无法连接 {url}（{exc.__class__.__name__}: {exc}）") from exc
        if resp.status_code >= 400:
            raise LlmError(
                f"{self.provider_name}/{self.model_name} HTTP {resp.status_code}: "
                f"{_error_message(_safe_json(resp), resp.text)}"
            )
        data = _safe_json(resp)
        if not isinstance(data, dict):
            raise LlmError(f"{self.provider_name}/{self.model_name} 响应不是 JSON 对象")
        if data.get("error") and not data.get("choices"):
            raise LlmError(_error_message(data, resp.text))
        self.last_usage = parse_usage(data.get("usage")) or parse_usage(data)
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LlmError(f"{self.provider_name}/{self.model_name} 响应缺少 choices")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        text = _content_text(message.get("content")) if isinstance(message, dict) else ""
        if not text:
            raise LlmError("模型响应缺少助手正文")
        return text

    async def stream_chat(
        self,
        prompt: str,
        *,
        system: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        merged = self._merged(kwargs)
        url = openai_chat_completions_url(self.base_url)
        payload = self._payload(prompt, system, merged, stream=True)
        self.last_usage = None
        try:
            async with httpx.AsyncClient(timeout=self._timeout(merged)) as client:
                async with client.stream(
                    "POST",
                    url,
                    headers=openai_auth_headers(self.api_key, json_body=True),
                    json=payload,
                ) as resp:
                    if resp.status_code >= 400:
                        raw = (await resp.aread()).decode("utf-8", errors="replace")
                        parsed = _loads_or_none(raw)
                        raise LlmError(
                            f"{self.provider_name}/{self.model_name} HTTP {resp.status_code}: "
                            f"{_error_message(parsed, raw)}"
                        )
                    has_text = False
                    async for payload_obj in _iter_stream_payloads(resp):
                        usage = parse_usage(payload_obj.get("usage")) or parse_usage(payload_obj)
                        if usage is not None:
                            self.last_usage = usage
                        if payload_obj.get("error") and not payload_obj.get("choices"):
                            raise LlmError(_error_message(payload_obj, ""))
                        text = _delta_text(payload_obj)
                        if text:
                            has_text = True
                            yield text
                    if not has_text:
                        raise LlmError("模型响应缺少助手正文")
        except LlmError:
            raise
        except httpx.HTTPError as exc:
            raise LlmError(f"无法连接 {url}（{exc.__class__.__name__}: {exc}）") from exc


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return None


def _loads_or_none(raw: str | bytes) -> Any:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def _delta_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return ""
    choice = choices[0]
    delta = choice.get("delta")
    if isinstance(delta, dict):
        text = _content_text(delta.get("content"))
        if text:
            return text
    message = choice.get("message")
    if isinstance(message, dict):
        return _content_text(message.get("content"))
    return ""


async def _iter_stream_payloads(resp: httpx.Response) -> AsyncIterator[dict[str, Any]]:
    """解析 SSE。若服务忽略 stream 并回了整段 JSON，也当成一次完成。"""
    if "application/json" in resp.headers.get("content-type", ""):
        raw = await resp.aread()
        parsed = _loads_or_none(raw)
        if not isinstance(parsed, dict):
            raise LlmError("模型响应不是 JSON 对象")
        yield parsed
        return

    finished = False
    async for line in resp.aiter_lines():
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            return
        if not data:
            continue
        event = _loads_or_none(data)
        if not isinstance(event, dict):
            raise LlmError("模型返回了无效的 SSE 数据")
        for choice in event.get("choices") or []:
            if isinstance(choice, dict) and choice.get("finish_reason"):
                finished = True
        yield event
    if not finished:
        raise LlmError("模型回复流提前结束")
