"""测试 provider registry + connection tester 的 URL 拼接。

不实际发请求；直接验 URL 拼接逻辑。
"""
from __future__ import annotations

from app.llm.provider_registry import (
    PROVIDERS,
    provider_names,
)


def test_registry_has_four_providers():
    assert provider_names() == ["minimax", "openai", "deepseek", "whisper"]


def test_default_base_urls_for_openai_compat_end_with_v1():
    """OpenAI-兼容路径（openai/minimax/whisper/deepseek）的 base_url 必须以 /v1 结尾。"""
    for name in ("openai", "minimax", "whisper", "deepseek"):
        spec = PROVIDERS[name]
        assert spec.default_base_url and spec.default_base_url.endswith("/v1"), (
            f"{name} default_base_url={spec.default_base_url} 应以 /v1 结尾"
        )


def test_test_url_path_does_not_double_v1():
    """确保 test_url_path 拼到 base_url 后只出现一次 /v1（OpenAI-兼容的 provider）。"""
    for name in ("openai", "minimax", "whisper", "deepseek"):
        spec = PROVIDERS[name]
        base = (spec.default_base_url or "").rstrip("/")
        url = f"{base}{spec.test_url_path}"
        count = url.count("/v1/")
        assert count == 1, f"{name} URL {url} 出现 {count} 次 /v1/"


def test_url_construction_user_supplied_base_url():
    """用户传入自定义 base_url 也要走 /models 不重复 /v1。"""
    spec = PROVIDERS["minimax"]
    user_base = "https://api.minimaxi.com/v1"
    base = user_base.rstrip("/")
    expected = f"{base}{spec.test_url_path}"
    assert expected == "https://api.minimaxi.com/v1/models"


def test_url_construction_default_minimax():
    """使用 provider registry 默认 base_url。"""
    spec = PROVIDERS["minimax"]
    base = (spec.default_base_url or "").rstrip("/")
    expected = f"{base}{spec.test_url_path}"
    assert expected == "https://api.minimax.chat/v1/models"


def test_url_construction_openai_default():
    spec = PROVIDERS["openai"]
    base = (spec.default_base_url or "").rstrip("/")
    expected = f"{base}{spec.test_url_path}"
    assert expected == "https://api.openai.com/v1/models"


def test_url_construction_whisper_default():
    spec = PROVIDERS["whisper"]
    base = (spec.default_base_url or "").rstrip("/")
    expected = f"{base}{spec.test_url_path}"
    assert expected == "https://api.openai.com/v1/models"
