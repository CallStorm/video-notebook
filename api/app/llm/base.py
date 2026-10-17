"""LLM provider 接口（基类）。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any


class LlmProvider(ABC):
    """provider = 一次构造对应一个 (provider_name, base_url, api_key, model_name)。"""

    def __init__(
        self,
        config_like: dict[str, Any],
        api_key: str,
        *,
        base_url: str | None = None,
        model_name: str | None = None,
        params_json: dict | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url or config_like.get("base_url")
        self.model_name = model_name or config_like.get("model_name", "")
        self.provider_name = config_like.get("provider", "")
        self.params_json = params_json or config_like.get("params_json") or {}

    @abstractmethod
    async def complete(self, prompt: str, *, system: str | None = None, **kwargs: Any) -> str:
        """非流式：返回完整助手回复。"""

    @abstractmethod
    async def stream_chat(
        self,
        prompt: str,
        *,
        system: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """流式：yield 字符串片段。Phase 7 接 SSE 用。"""


class LlmError(Exception):
    """provider 调用错误包装。"""
