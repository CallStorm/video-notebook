"""内建 LLM 追踪（类 Langfuse 轻量版）。"""
from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any

from app.observability.settings_cache import get_flags
from app.observability.writer import enqueue

_seq: dict[str, int] = {}


def start_llm_trace(
    *,
    kind: str,
    notebook_id: int | None = None,
    video_id: int | None = None,
    thread_id: int | None = None,
    provider: str | None = None,
    model_name: str | None = None,
) -> str | None:
    flags = get_flags()
    if not flags.llm_traces_enabled:
        return None
    tid = str(uuid.uuid4())
    _seq[tid] = 0
    enqueue(
        {
            "op": "llm_trace_upsert",
            "trace_id": tid,
            "kind": kind,
            "status": "running",
            "notebook_id": notebook_id,
            "video_id": video_id,
            "thread_id": thread_id,
            "provider": provider,
            "model_name": model_name,
            "started_at": datetime.utcnow().isoformat(),
        }
    )
    return tid


def llm_span(
    trace_id: str | None,
    name: str,
    *,
    content: str | None = None,
    role: str | None = None,
) -> None:
    if not trace_id:
        return
    flags = get_flags()
    if not flags.llm_traces_enabled:
        return
    raw = content or ""
    chars = len(raw)
    trunc_n = flags.llm_truncate_chars
    truncated = False
    stored = raw
    if not flags.llm_record_full and chars > trunc_n:
        stored = raw[:trunc_n] + f"\n…[截断 {chars - trunc_n} 字符]"
        truncated = True
    n = _seq.get(trace_id, 0) + 1
    _seq[trace_id] = n
    enqueue(
        {
            "op": "llm_span",
            "trace_id": trace_id,
            "seq": n,
            "name": name,
            "role": role,
            "content_text": stored or None,
            "content_chars": chars,
            "truncated": truncated,
            "created_at": datetime.utcnow().isoformat(),
        }
    )


def end_llm_trace(
    trace_id: str | None,
    *,
    status: str = "ok",
    error_text: str | None = None,
    message_id: int | None = None,
    latency_ms: int | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    t0: float | None = None,
) -> None:
    if not trace_id:
        return
    flags = get_flags()
    if not flags.llm_traces_enabled:
        return
    ms = latency_ms
    if ms is None and t0 is not None:
        ms = int((time.perf_counter() - t0) * 1000)
    enqueue(
        {
            "op": "llm_trace_upsert",
            "trace_id": trace_id,
            "status": status,
            "error_text": (error_text or "")[:4000] or None,
            "message_id": message_id,
            "latency_ms": ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "finished_at": datetime.utcnow().isoformat(),
        }
    )
    _seq.pop(trace_id, None)
