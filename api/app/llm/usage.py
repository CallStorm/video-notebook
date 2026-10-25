"""Normalize LLM token usage across Anthropic / OpenAI-style payloads."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None

    @property
    def total_tokens(self) -> int | None:
        if self.prompt_tokens is None and self.completion_tokens is None:
            return None
        return int(self.prompt_tokens or 0) + int(self.completion_tokens or 0)


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n >= 0 else None


def parse_usage(raw: Any) -> TokenUsage | None:
    """Accept Anthropic Message.usage, OpenAI usage dict, or similar objects.

    Recognized keys:
    - prompt_tokens / completion_tokens / total_tokens (OpenAI)
    - input_tokens / output_tokens (Anthropic)
    """
    if raw is None:
        return None

    if isinstance(raw, TokenUsage):
        return raw

    data: dict[str, Any]
    if isinstance(raw, dict):
        data = raw
    else:
        # pydantic/SDK model or SimpleNamespace
        data = {}
        for key in (
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "input_tokens",
            "output_tokens",
        ):
            if hasattr(raw, key):
                data[key] = getattr(raw, key)
        # nested .usage
        if not data and hasattr(raw, "usage"):
            return parse_usage(getattr(raw, "usage"))

    prompt = _as_int(data.get("prompt_tokens"))
    if prompt is None:
        prompt = _as_int(data.get("input_tokens"))
    completion = _as_int(data.get("completion_tokens"))
    if completion is None:
        completion = _as_int(data.get("output_tokens"))
    total = _as_int(data.get("total_tokens"))

    if prompt is None and completion is None and total is None:
        return None
    if prompt is None and completion is None and total is not None:
        # only total known — keep as prompt so SUM still moves; rare
        prompt = total
        completion = 0
    return TokenUsage(prompt_tokens=prompt, completion_tokens=completion)
