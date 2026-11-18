"""把后台选中的语音转文字模型解析成转写后端。

默认仍是 OpenAI 兼容的 `/audio/transcriptions`（provider 为 openai 或 whisper）。
进程内模型和本地 HTTP 服务用新的 provider，也可以在凭证 config.backend 里指定。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.llm.config_service import SttResolved

OPENAI_COMPAT_PROVIDERS = frozenset({"openai", "whisper"})

_BACKEND_ALIASES = {
    "openai": "openai_compat",
    "hosted": "openai_compat",
    "openai_compat": "openai_compat",
    "faster_whisper": "faster_whisper",
    "fasterwhisper": "faster_whisper",
    "whisper_cpp": "whisper_cpp",
    "whispercpp": "whisper_cpp",
    "http_openai": "http_openai",
    "asr_server": "http_openai",
    "http_whisper_cpp": "http_whisper_cpp",
    "whisper_cpp_server": "http_whisper_cpp",
}


class AsrConfigError(ValueError):
    """用户选了无法识别的语音转写后端。"""


@dataclass(frozen=True)
class AsrSettings:
    backend: str
    provider: str
    model: str
    endpoint: str | None
    language: str | None
    api_key: str | None
    device: str
    compute_type: str
    threads: int | None
    vad_filter: bool
    timeout_seconds: float
    download_root: str | None


def config_dict(config: dict | None) -> dict[str, Any]:
    return config if isinstance(config, dict) else {}


def language_from_config(config: dict | None) -> str | None:
    """空字符串和 auto 表示自动检测，不传给引擎。"""
    raw = config_dict(config).get("language")
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.lower() == "auto":
        return None
    return text[:16]


def model_ref(stt: SttResolved) -> str:
    """模型名，或凭证 config.model_path（长路径放这里，优先于模型名）。"""
    cfg = config_dict(stt.config)
    for key in ("model_path", "model"):
        raw = cfg.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return (stt.model_name or "").strip()


def http_backend(config: dict | None) -> str:
    protocol = str(config_dict(config).get("protocol") or "openai").strip().lower()
    protocol = protocol.replace("-", "_").replace(".", "_")
    if protocol in {"whisper_cpp", "whispercpp", "inference"}:
        return "http_whisper_cpp"
    return "http_openai"


def backend_kind(stt: SttResolved) -> str:
    """返回 openai_compat / faster_whisper / whisper_cpp / http_openai / http_whisper_cpp。"""
    cfg = config_dict(stt.config)
    override = cfg.get("backend")
    if isinstance(override, str) and override.strip():
        key = override.strip().lower().replace("-", "_")
        if key == "http":
            return http_backend(cfg)
        mapped = _BACKEND_ALIASES.get(key)
        if mapped is None:
            raise AsrConfigError(f"不支持的语音转写后端 {override.strip()}")
        return mapped

    provider = (stt.provider or "").strip()
    if provider in OPENAI_COMPAT_PROVIDERS:
        return "openai_compat"
    if provider == "faster_whisper":
        return "faster_whisper"
    if provider == "whisper_cpp":
        return "whisper_cpp"
    if provider == "asr_server":
        return http_backend(cfg)
    raise AsrConfigError(f"当前语音转文字供应商 {provider or '未设置'} 还不支持自动转写")


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float):
        return int(value) if value > 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        return parsed if parsed > 0 else None
    return None


def _bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def settings_from_stt(stt: SttResolved) -> AsrSettings:
    cfg = config_dict(stt.config)
    timeout_raw = cfg.get("timeout_seconds")
    try:
        timeout = float(timeout_raw) if timeout_raw is not None else 600.0
    except (TypeError, ValueError):
        timeout = 600.0
    download_root = cfg.get("download_root")
    endpoint = (stt.base_url or "").strip() or None
    return AsrSettings(
        backend=backend_kind(stt),
        provider=stt.provider,
        model=model_ref(stt),
        endpoint=endpoint,
        language=language_from_config(cfg),
        api_key=(stt.api_key or "").strip() or None,
        device=str(cfg.get("device") or "auto").strip() or "auto",
        compute_type=str(cfg.get("compute_type") or "default").strip() or "default",
        threads=_optional_int(cfg.get("threads")),
        vad_filter=_bool(cfg.get("vad_filter"), True),
        timeout_seconds=timeout if timeout > 0 else 600.0,
        download_root=(
            str(download_root).strip()
            if isinstance(download_root, str) and download_root.strip()
            else None
        ),
    )
