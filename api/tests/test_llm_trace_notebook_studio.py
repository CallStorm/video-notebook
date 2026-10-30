"""P0/P1: notebook_id on chat/overview traces; studio start/end when enabled."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.observability import llm_trace


@pytest.mark.asyncio
async def test_chat_start_llm_trace_includes_notebook_id(monkeypatch):
    calls: list[dict] = []

    def fake_start(**kwargs):
        calls.append(kwargs)
        return "trace-chat-1"

    from app.chat import service as chat_service

    monkeypatch.setattr(chat_service, "start_llm_trace", fake_start)
    monkeypatch.setattr(chat_service, "llm_span", lambda *a, **k: None)
    monkeypatch.setattr(chat_service, "end_llm_trace", lambda *a, **k: None)

    class FakeProvider:
        last_usage = None

        async def stream_chat(self, *args, **kwargs):
            yield "你好"
            return
            yield  # pragma: no cover

    monkeypatch.setattr(chat_service, "make_provider", lambda **kw: FakeProvider())

    async def fake_save(prepared, text, citations):
        return 99

    monkeypatch.setattr(chat_service, "_save_assistant", fake_save)

    prepared = chat_service.PreparedChat(
        thread_id=7,
        notebook_id=42,
        prompt="问题：hi",
        history=[],
        context=SimpleNamespace(lines=[], source_ids=[]),
        llm=SimpleNamespace(
            provider="openai",
            api_key="k",
            base_url=None,
            model_name="m",
            params_json={},
        ),
        system="sys",
    )
    events = [e async for e in chat_service.stream_answer(prepared)]
    assert any(e.get("type") == "done" for e in events)
    assert calls and calls[0]["kind"] == "chat"
    assert calls[0]["notebook_id"] == 42
    assert calls[0]["thread_id"] == 7


@pytest.mark.asyncio
async def test_overview_start_llm_trace_includes_notebook_id(monkeypatch, db_session):
    calls: list[dict] = []

    def fake_start(**kwargs):
        calls.append(kwargs)
        return "trace-ov-1"

    from app.subtitles import overview as overview_mod

    monkeypatch.setattr(overview_mod, "start_llm_trace", fake_start)
    monkeypatch.setattr(overview_mod, "llm_span", lambda *a, **k: None)
    monkeypatch.setattr(overview_mod, "end_llm_trace", lambda *a, **k: None)

    class FakeProvider:
        last_usage = None

        async def complete(self, *args, **kwargs):
            return "这是概览"

    async def fake_llm(session):
        return SimpleNamespace(
            provider="openai",
            api_key="k",
            base_url=None,
            model_name="m",
            params_json={},
        )

    monkeypatch.setattr(overview_mod, "get_active_llm", fake_llm)
    monkeypatch.setattr(overview_mod, "make_provider", lambda **kw: FakeProvider())
    monkeypatch.setattr(
        overview_mod,
        "get_overview_settings_row",
        AsyncMock(return_value=SimpleNamespace(prompt_text=None)),
    )
    monkeypatch.setattr(overview_mod, "resolve_prompt", lambda row: "写概览")

    line = SimpleNamespace(text="字幕一行")
    video = SimpleNamespace(id=5, title="标题")
    text = await overview_mod.write_overview(
        db_session, [line], video=video, notebook_id=88
    )
    assert text.startswith("这是")
    assert calls and calls[0]["kind"] == "overview"
    assert calls[0]["notebook_id"] == 88
    assert calls[0]["video_id"] == 5


_MINDMAP_PY = r'''
import json
import sys
from pathlib import Path
sys.stdin.read()
out = Path("outputs")
out.mkdir(parents=True, exist_ok=True)
(out / "mindmap.md").write_text("# 灭佛\n", encoding="utf-8")
(out / "MANIFEST.json").write_text(
    json.dumps(
        {
            "version": 1,
            "status": "success",
            "title": "自动标题",
            "artifacts": [
                {
                    "role": "main",
                    "path": "outputs/mindmap.md",
                    "mime": "text/markdown",
                }
            ],
        },
        ensure_ascii=False,
    ),
    encoding="utf-8",
)
'''


@pytest.mark.asyncio
async def test_studio_execute_calls_start_and_end_when_tracing_on(
    db_session, tmp_path, monkeypatch
):
    from app.studio import runner as runner_mod
    from tests.test_studio_runner import _seed, _windows_safe_claude

    starts: list[dict] = []
    ends: list[dict] = []
    spans: list[tuple] = []

    def fake_start(**kwargs):
        starts.append(kwargs)
        return "studio-trace-1"

    def fake_end(trace_id, **kwargs):
        ends.append({"trace_id": trace_id, **kwargs})

    def fake_span(trace_id, name, **kwargs):
        spans.append((trace_id, name, kwargs))

    monkeypatch.setattr(runner_mod, "start_llm_trace", fake_start)
    monkeypatch.setattr(runner_mod, "end_llm_trace", fake_end)
    monkeypatch.setattr(runner_mod, "llm_span", fake_span)

    script = _windows_safe_claude(tmp_path / "claude", _MINDMAP_PY)
    task, _video, _note = await _seed(db_session)
    await runner_mod.execute_studio_task(task.id, claude_bin=str(script))
    await db_session.refresh(task)
    assert task.status == "succeeded", (task.error_code, task.error_message)
    assert len(starts) == 1
    assert starts[0]["kind"] == "studio"
    assert starts[0]["notebook_id"] == task.notebook_id
    assert starts[0]["provider"] == "claude_code"
    assert len(ends) == 1
    assert ends[0]["trace_id"] == "studio-trace-1"
    assert ends[0]["status"] == "ok"
    names = [s[1] for s in spans]
    assert "task_meta" in names
    assert "prompt" in names


@pytest.mark.asyncio
async def test_studio_execute_skips_trace_when_disabled(
    db_session, tmp_path, monkeypatch
):
    from app.studio import runner as runner_mod
    from tests.test_studio_runner import _seed, _windows_safe_claude

    ends: list = []

    monkeypatch.setattr(runner_mod, "start_llm_trace", lambda **kwargs: None)
    monkeypatch.setattr(
        runner_mod, "end_llm_trace", lambda *a, **k: ends.append(1)
    )
    monkeypatch.setattr(runner_mod, "llm_span", lambda *a, **k: None)

    script = _windows_safe_claude(tmp_path / "claude", _MINDMAP_PY)
    task, _v, _n = await _seed(db_session)
    await runner_mod.execute_studio_task(task.id, claude_bin=str(script))
    await db_session.refresh(task)
    assert task.status == "succeeded", (task.error_code, task.error_message)
    assert ends == [1]
