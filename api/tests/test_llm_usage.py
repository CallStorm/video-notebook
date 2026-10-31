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


def test_parse_model_dump_message():
    class Msg:
        def model_dump(self):
            return {"usage": {"input_tokens": 7, "output_tokens": 9}}

    usage = parse_usage(Msg())
    assert usage == TokenUsage(prompt_tokens=7, completion_tokens=9)
    assert usage.total_tokens == 16
