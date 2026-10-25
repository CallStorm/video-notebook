"""可观测：关闭时不写；队列溢出不抛。"""
from __future__ import annotations

from app.observability import pipeline_log, llm_trace
from app.observability.settings_cache import ObsFlags
from app.observability import writer


def test_pipeline_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(
        pipeline_log, "get_flags", lambda: ObsFlags(pipeline_logs_enabled=False)
    )
    assert pipeline_log.start_pipeline_run(video_id=1) is None
    pipeline_log.log_event("fetch", "ok")  # must not raise


def test_llm_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(
        llm_trace, "get_flags", lambda: ObsFlags(llm_traces_enabled=False)
    )
    assert llm_trace.start_llm_trace(kind="chat") is None
    llm_trace.llm_span(None, "user", content="x")


def test_enqueue_never_raises_on_overflow(monkeypatch):
    # shrink queue
    monkeypatch.setattr(writer, "_QUEUE_MAX", 2)
    # replace queue
    import queue as qmod

    writer._q = qmod.Queue(maxsize=2)
    for i in range(20):
        writer.enqueue({"op": "purge", "n": i})
