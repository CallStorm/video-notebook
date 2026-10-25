"""Token usage normalization."""
from types import SimpleNamespace

from app.llm.usage import TokenUsage, parse_usage


def test_parse_anthropic_usage_object():
    usage = parse_usage(SimpleNamespace(input_tokens=12, output_tokens=34))
    assert usage == TokenUsage(prompt_tokens=12, completion_tokens=34)
    assert usage.total_tokens == 46


def test_parse_openai_usage_dict():
    usage = parse_usage({"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30})
    assert usage == TokenUsage(prompt_tokens=10, completion_tokens=20)


def test_parse_nested_usage():
    usage = parse_usage(SimpleNamespace(usage={"input_tokens": 1, "output_tokens": 2}))
    assert usage == TokenUsage(prompt_tokens=1, completion_tokens=2)


def test_parse_empty():
    assert parse_usage(None) is None
    assert parse_usage({}) is None
