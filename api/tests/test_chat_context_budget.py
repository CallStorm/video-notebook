"""对话上下文：全量勾选 + N 轮历史预算。"""
from __future__ import annotations

from app.chat.service import _last_n_turns, _trim_history_to_budget


def test_last_n_turns_keeps_pairs():
    history = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "q2"},
        {"role": "assistant", "content": "a2"},
        {"role": "user", "content": "q3"},
        {"role": "assistant", "content": "a3"},
    ]
    kept = _last_n_turns(history, 2)
    assert [item["content"] for item in kept] == ["q2", "a2", "q3", "a3"]


def test_trim_history_drops_oldest_first():
    history = [
        {"role": "user", "content": "old" * 100},
        {"role": "assistant", "content": "old-a" * 100},
        {"role": "user", "content": "new"},
        {"role": "assistant", "content": "new-a"},
    ]
    # fixed 接近上限，迫使丢掉旧轮
    fixed = 59_500
    max_chars = 60_000
    out, trimmed = _trim_history_to_budget(history, fixed_chars=fixed, max_chars=max_chars)
    assert trimmed is True
    assert all("old" not in item["content"] for item in out)
    assert any(item["content"] == "new" for item in out)


def test_trim_history_noop_when_fits():
    history = [
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": "a"},
    ]
    out, trimmed = _trim_history_to_budget(history, fixed_chars=100, max_chars=60_000)
    assert trimmed is False
    assert out == history
