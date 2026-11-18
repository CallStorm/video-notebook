"""检查本地 ASR 是否装好、模型路径是否在、服务是否开着。不真正转写。"""
from __future__ import annotations

import importlib.util
import shutil
import time
from pathlib import Path

import httpx

from app.asr.settings import http_backend


def _result(
    *,
    provider: str,
    started: float,
    ok: bool,
    message: str | None = None,
    error: str | None = None,
) -> dict:
    return {
        "ok": ok,
        "latency_ms": int((time.monotonic() - started) * 1000),
        "provider": provider,
        "message": message,
        "error": error,
    }


def _explicit_path(model: str) -> bool:
    if model.startswith(("/", "~", "./", "../")):
        return True
    if model.endswith(".bin"):
        return True
    return len(model) > 2 and model[1] == ":"


def _model_path_error(model: str | None, *, require_file: bool) -> str | None:
    cleaned = (model or "").strip()
    if not cleaned:
        return "请填写模型名或模型路径" if require_file else None
    if _explicit_path(cleaned) or require_file:
        path = Path(cleaned).expanduser()
        if require_file and not path.is_file():
            return f"模型文件不存在: {cleaned}"
        if not require_file and _explicit_path(cleaned) and not path.exists():
            return f"模型路径不存在: {cleaned}"
    return None


async def probe_stt(
    *,
    provider: str,
    api_key: str = "",
    base_url: str | None = None,
    config: dict | None = None,
    model_name: str | None = None,
) -> dict:
    started = time.monotonic()
    cfg = config if isinstance(config, dict) else {}
    model = str(cfg.get("model_path") or model_name or "").strip()
    if provider == "faster_whisper":
        if importlib.util.find_spec("faster_whisper") is None:
            return _result(
                provider=provider,
                started=started,
                ok=False,
                error="未安装 faster-whisper。在 api 目录执行：uv sync --extra asr",
            )
        path_error = _model_path_error(model, require_file=False)
        if path_error and model:
            return _result(provider=provider, started=started, ok=False, error=path_error)
        label = model or "（首次转写时按模型名下载）"
        return _result(
            provider=provider,
            started=started,
            ok=True,
            message=f"faster-whisper 已安装，模型 {label}",
        )
    if provider == "whisper_cpp":
        engine = str(cfg.get("engine") or "auto").strip().lower()
        cli = shutil.which("whisper-cli") or shutil.which("whisper-cpp")
        py_ok = importlib.util.find_spec("pywhispercpp") is not None
        if engine == "cli" and not cli:
            return _result(
                provider=provider,
                started=started,
                ok=False,
                error="未找到 whisper-cli。请安装 whisper.cpp 并加入 PATH。",
            )
        if engine == "pywhispercpp" and not py_ok:
            return _result(
                provider=provider,
                started=started,
                ok=False,
                error="未安装 pywhispercpp。",
            )
        if engine == "auto" and not cli and not py_ok:
            return _result(
                provider=provider,
                started=started,
                ok=False,
                error="未找到 whisper-cli，也未安装 pywhispercpp。",
            )
        path_error = _model_path_error(model, require_file=bool(model))
        if path_error:
            return _result(provider=provider, started=started, ok=False, error=path_error)
        how = cli or "pywhispercpp"
        return _result(
            provider=provider,
            started=started,
            ok=True,
            message=f"whisper.cpp 可用（{how}）" + (f"，模型 {model}" if model else ""),
        )
    if provider == "asr_server":
        return await _probe_http(
            provider=provider,
            started=started,
            base_url=base_url,
            api_key=api_key,
            config=cfg,
        )
    return _result(
        provider=provider,
        started=started,
        ok=False,
        error=f"没有针对 {provider} 的本地探测",
    )


async def _probe_http(
    *,
    provider: str,
    started: float,
    base_url: str | None,
    api_key: str,
    config: dict,
) -> dict:
    base = (base_url or "").strip().rstrip("/")
    if not base:
        return _result(
            provider=provider,
            started=started,
            ok=False,
            error="本地 ASR 服务需要填写 endpoint URL（Base URL）",
        )
    kind = http_backend(config)
    url = base if kind == "http_whisper_cpp" else f"{base}/models"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        return _result(
            provider=provider,
            started=started,
            ok=False,
            error=f"无法连接 {url}: {exc.__class__.__name__}",
        )
    if not response.is_success:
        return _result(
            provider=provider,
            started=started,
            ok=False,
            error=f"ASR 服务 HTTP {response.status_code}: {response.text[:200]}",
        )
    return _result(
        provider=provider,
        started=started,
        ok=True,
        message=f"ASR 服务可达（HTTP {response.status_code} {url}）",
    )
