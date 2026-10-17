"""Provider Registry — 单一可信源

参考 open-notebook/open_notebook/ai/provider_registry.py 的设计，做精简版：

- 1 个 frozen `ProviderSpec` dataclass 装元数据
- 1 个 `PROVIDERS` dict：name → spec
- 后端的 connection_tester / admin APIs / 前端的下拉 / Schema 的枚举都从这里读

添加 provider = 在 `_PROVIDER_SPECS` 元组里加一项即可。LLM/ASR 通用。
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ── 类型 ────────────────────────────────────────────────────────────────
LLM = "language"
STT = "speech_to_text"
TTS = "text_to_speech"
EMBEDDING = "embedding"

ALL_MODALITIES: tuple[str, ...] = (LLM, EMBEDDING, STT, TTS)
LANGUAGE_ONLY: tuple[str, ...] = (LLM,)
STT_ONLY: tuple[str, ...] = (STT,)


@dataclass(frozen=True)
class ProviderSpec:
    """Everything backend needs to know about one AI provider."""

    name: str
    display_name: str
    """Provider 暴露的能力。"""
    modalities: tuple[str, ...]

    # ─── 默认 / 测试用 ─────────────────────────────────────────────
    default_base_url: str | None = None
    """Provider 默认 base URL；调用方可不填 base_url 用此值。"""
    test_model: str | None = None
    """便宜模型，做连通性测试用。None 表示该 provider 用 GET /v1/models 即可。"""
    test_url_path: str = "/models"
    """OpenAI-兼容测试路径。default_base_url 已含 /v1，这里只补 /models。
    若 provider 的 base_url 不带 /v1，override test_url_path='/v1/models'。"""
    docs_url: str | None = None

    # ─── 厂商特性 ────────────────────────────────────────────────────
    anthropic_compat: bool = False
    """Provider 走 Anthropic-兼容 SDK（minimax 走这种）。"""
    requires_api_key: bool = True

    # 一些 provider 有额外字段（如 Azure 的 api_version）。v1 用 config 字典承载。
    extra_required_fields: tuple[str, ...] = field(default_factory=tuple)


# ─── Provider 元数据 ─────────────────────────────────────────────────────
# v1 锁 4 个 provider：
# - minimax : chat + tts （走 Anthropic-兼容 SDK）
# - openai   : chat + tts + stt + embedding
# - deepseek : chat （OpenAI 兼容）
# - whisper  : stt （OpenAI Whisper API）
_PROVIDER_SPECS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        name="minimax",
        display_name="MiniMax",
        modalities=(LLM, TTS),
        default_base_url="https://api.minimax.chat/v1",
        test_model="MiniMax-M3",
        docs_url="https://platform.minimaxi.com/document/Guides",
        anthropic_compat=True,
    ),
    ProviderSpec(
        name="openai",
        display_name="OpenAI",
        modalities=ALL_MODALITIES,
        default_base_url="https://api.openai.com/v1",
        test_model="gpt-3.5-turbo",
        docs_url="https://platform.openai.com/api-keys",
    ),
    ProviderSpec(
        name="deepseek",
        display_name="DeepSeek",
        modalities=LANGUAGE_ONLY,
        default_base_url="https://api.deepseek.com/v1",
        test_model="deepseek-chat",
        docs_url="https://platform.deepseek.com/api_keys",
    ),
    ProviderSpec(
        name="whisper",
        display_name="OpenAI Whisper (ASR)",
        modalities=STT_ONLY,
        default_base_url="https://api.openai.com/v1",
        test_model=None,
        docs_url="https://platform.openai.com/api-keys",
    ),
)


PROVIDERS: dict[str, ProviderSpec] = {spec.name: spec for spec in _PROVIDER_SPECS}


def get_provider(name: str) -> ProviderSpec | None:
    return PROVIDERS.get(name)


def provider_names() -> list[str]:
    return [s.name for s in _PROVIDER_SPECS]


def llm_providers() -> list[ProviderSpec]:
    """返回支持 language 模态的 provider 列表（用作 LLM role 选项）。"""
    return [s for s in _PROVIDER_SPECS if LLM in s.modalities]


def stt_providers() -> list[ProviderSpec]:
    """返回支持 STT 的 provider 列表。"""
    return [s for s in _PROVIDER_SPECS if STT in s.modalities]


def assert_provider_exists(name: str) -> ProviderSpec:
    from app.core.errors import BadRequestError

    spec = PROVIDERS.get(name)
    if spec is None:
        raise BadRequestError(f"unknown provider: {name}; known: {provider_names()}")
    return spec
