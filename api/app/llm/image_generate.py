"""Text-to-image: OpenAI-compatible + MiniMax image_generation."""
from __future__ import annotations

import base64
import logging
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.core.errors import BadRequestError, ServiceUnavailableError

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 120.0
# Small portrait for notebook covers (cards are ~4:5 / 5:7).
_DEFAULT_SIZE = "512x768"

_STRIP_SUFFIXES = (
    "/chat/completions",
    "/completions",
    "/messages",
    "/images/generations",
    "/image_generation",
    "/images",
    "/models",
    "/anthropic",
)

_SIZE_RE = re.compile(r"^(\d{2,4})x(\d{2,4})$", re.I)
_RATIO_RE = re.compile(r"^(\d{1,2}):(\d{1,2})$")

# MiniMax documented aspect ratios (portrait preferred for covers).
_MINIMAX_RATIOS = {
    "1:1",
    "16:9",
    "4:3",
    "3:2",
    "2:3",
    "3:4",
    "9:16",
    "21:9",
}

_MSG_404_OPENAI = (
    "当前模型/网关不支持 OpenAI 文生图接口 /v1/images/generations；"
    "请配置真正的出图模型（如 SiliconFlow FLUX / Kolors、OpenAI dall-e），"
    "或改用 MiniMax 的 image-01（走 /v1/image_generation）。"
    "多模态对话模型不能用来出图。"
)

_MSG_MINIMAX_CHAT_MODEL = (
    "MiniMax 封面文生图请将模型名设为 image-01（或 image-01-live），"
    "不要使用聊天模型（如 MiniMax-M3）。同一凭证/base_url 即可。"
)


def is_minimax_image(*, base_url: str | None, model_name: str, provider: str | None = None) -> bool:
    """Detect MiniMax image API (not OpenAI /images/generations)."""
    prov = (provider or "").strip().lower()
    if prov == "minimax":
        return True
    host = ""
    if base_url:
        host = (urlsplit(base_url.strip()).hostname or "").lower()
    if "minimax" in host or "minimaxi" in host:
        return True
    name = (model_name or "").strip().lower()
    if name.startswith("image-01"):
        return True
    return False


def openai_images_base_url(base_url: str | None) -> str:
    """Normalize to .../v1 for OpenAI-compatible /images/generations."""
    raw = (base_url or "https://api.openai.com/v1").strip().rstrip("/")
    parsed = urlsplit(raw)
    path = parsed.path.rstrip("/") or ""
    lowered = path.lower()
    for suffix in _STRIP_SUFFIXES:
        if lowered.endswith(suffix):
            path = path[: -len(suffix)].rstrip("/")
            lowered = path.lower()
            break
    if not path.endswith("/v1"):
        path = f"{path}/v1" if path else "/v1"
    return urlunsplit((parsed.scheme or "https", parsed.netloc, path, "", "")).rstrip("/")


def openai_images_generations_url(base_url: str | None) -> str:
    return f"{openai_images_base_url(base_url)}/images/generations"


def minimax_image_base_url(base_url: str | None) -> str:
    """Normalize MiniMax base to .../v1 for POST /image_generation.

    Keeps the configured host (api.minimax.cn / .io / minimaxi.com).
    Strips /anthropic and chat/image endpoint footguns.
    """
    raw = (base_url or "https://api.minimax.cn/v1").strip().rstrip("/")
    parsed = urlsplit(raw)
    path = parsed.path.rstrip("/") or ""
    lowered = path.lower()
    for suffix in _STRIP_SUFFIXES:
        if lowered.endswith(suffix):
            path = path[: -len(suffix)].rstrip("/")
            lowered = path.lower()
            break
    if not path.endswith("/v1"):
        path = f"{path}/v1" if path else "/v1"
    return urlunsplit((parsed.scheme or "https", parsed.netloc, path, "", "")).rstrip("/")


def minimax_image_generation_url(base_url: str | None) -> str:
    return f"{minimax_image_base_url(base_url)}/image_generation"


def parse_size_token(size: str | None) -> tuple[str | None, int | None, int | None]:
    """Return (aspect_ratio, width, height). Prefer ratio when size is like 3:4."""
    raw = (size or _DEFAULT_SIZE).strip()
    if not raw:
        raw = _DEFAULT_SIZE
    if _RATIO_RE.match(raw) and raw in _MINIMAX_RATIOS:
        return raw, None, None
    m = _SIZE_RE.match(raw)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        return None, w, h
    # Unknown token → small portrait
    return "3:4", None, None


def size_for_openai(size: str | None) -> str:
    """Map config size/ratio to OpenAI-compat `size` string."""
    ratio, w, h = parse_size_token(size)
    if w and h:
        return f"{w}x{h}"
    # Map common ratios to WxH for SiliconFlow / DALL-E-ish gateways
    mapping = {
        "1:1": "1024x1024",
        "3:4": "768x1024",
        "2:3": "768x1152",
        "9:16": "576x1024",
        "4:3": "1024x768",
        "16:9": "1280x720",
    }
    if ratio and ratio in mapping:
        return mapping[ratio]
    return _DEFAULT_SIZE


def minimax_size_payload(size: str | None) -> dict[str, Any]:
    """Build aspect_ratio or width/height for MiniMax. Prefer small portrait."""
    ratio, w, h = parse_size_token(size)
    if ratio:
        return {"aspect_ratio": ratio}
    assert w is not None and h is not None
    # MiniMax requires [512,2048] and divisible by 8
    w = max(512, min(2048, (w // 8) * 8))
    h = max(512, min(2048, (h // 8) * 8))
    return {"width": w, "height": h}


def resolve_minimax_model(model_name: str) -> str:
    name = (model_name or "").strip()
    low = name.lower()
    if low in ("image-01", "image-01-live") or low.startswith("image-01"):
        return name if low.startswith("image-01") else name
    # Chat / VL models bound by mistake
    raise BadRequestError(_MSG_MINIMAX_CHAT_MODEL)


def _format_http_error(status_code: int, detail: str, *, minimax: bool = False) -> str:
    detail = (detail or "").strip()
    if status_code == 404:
        if minimax:
            msg = (
                "MiniMax 文生图接口未找到。请确认 base_url 指向 "
                "https://api.minimax.cn 或 https://api.minimax.io（或现有 minimaxi 主机），"
                "路径为 /v1/image_generation；模型名用 image-01。"
            )
        else:
            msg = _MSG_404_OPENAI
        extra = f"（网关返回：{detail}）" if detail else ""
        return f"文生图失败（HTTP 404）：{msg}{extra}"
    if detail:
        return f"文生图失败（HTTP {status_code}）：{detail}"
    return f"文生图失败（HTTP {status_code}）"


async def generate_image_bytes(
    *,
    api_key: str,
    base_url: str | None,
    model_name: str,
    prompt: str,
    size: str = _DEFAULT_SIZE,
    timeout: float = _DEFAULT_TIMEOUT,
    provider: str | None = None,
) -> tuple[bytes, str]:
    """Generate one image. MiniMax → /v1/image_generation; else OpenAI /images/generations."""
    if not (api_key or "").strip():
        raise BadRequestError("文生图模型未配置 API Key")
    if not (model_name or "").strip():
        raise BadRequestError("文生图模型名称为空")
    if not (prompt or "").strip():
        raise BadRequestError("文生图提示词为空")

    if is_minimax_image(base_url=base_url, model_name=model_name, provider=provider):
        return await _generate_minimax(
            api_key=api_key.strip(),
            base_url=base_url,
            model_name=model_name,
            prompt=prompt.strip()[:1500],
            size=size,
            timeout=timeout,
        )
    return await _generate_openai(
        api_key=api_key.strip(),
        base_url=base_url,
        model_name=model_name.strip(),
        prompt=prompt.strip(),
        size=size,
        timeout=timeout,
    )


async def _generate_minimax(
    *,
    api_key: str,
    base_url: str | None,
    model_name: str,
    prompt: str,
    size: str | None,
    timeout: float,
) -> tuple[bytes, str]:
    model = resolve_minimax_model(model_name)
    url = minimax_image_generation_url(base_url)
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "response_format": "base64",
        "prompt_optimizer": True,
        **minimax_size_payload(size),
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    logger.info("minimax image_generation POST %s model=%s size=%s", url, model, size)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException as exc:
        raise ServiceUnavailableError("文生图请求超时，请稍后重试") from exc
    except httpx.HTTPError as exc:
        raise ServiceUnavailableError(f"文生图网络错误：{exc}") from exc

    if resp.status_code >= 400:
        raise ServiceUnavailableError(
            _format_http_error(resp.status_code, _safe_error_detail(resp), minimax=True)
        )

    try:
        body = resp.json()
    except Exception as exc:
        raise ServiceUnavailableError("文生图返回无法解析的 JSON") from exc

    if not isinstance(body, dict):
        raise ServiceUnavailableError("文生图返回格式异常")

    base_resp = body.get("base_resp")
    if isinstance(base_resp, dict):
        code = base_resp.get("status_code")
        if code not in (0, "0", None):
            msg = str(base_resp.get("status_msg") or f"status_code={code}")[:400]
            raise ServiceUnavailableError(f"文生图失败（MiniMax {code}）：{msg}")

    data = body.get("data")
    if not isinstance(data, dict):
        raise ServiceUnavailableError("文生图未返回图片数据")

    b64_list = data.get("image_base64")
    if isinstance(b64_list, list) and b64_list:
        first = b64_list[0]
        if isinstance(first, str) and first.strip():
            try:
                raw = base64.b64decode(first)
            except Exception as exc:
                raise ServiceUnavailableError("文生图 base64 解码失败") from exc
            return raw, _sniff_content_type(raw)

    url_list = data.get("image_urls")
    if isinstance(url_list, list) and url_list:
        image_url = url_list[0]
        if isinstance(image_url, str) and image_url.startswith(("http://", "https://")):
            return await _download_image(image_url, timeout=timeout)

    raise ServiceUnavailableError("文生图响应缺少 image_base64 / image_urls")


async def _generate_openai(
    *,
    api_key: str,
    base_url: str | None,
    model_name: str,
    prompt: str,
    size: str | None,
    timeout: float,
) -> tuple[bytes, str]:
    url = openai_images_generations_url(base_url)
    payload: dict[str, Any] = {
        "model": model_name,
        "prompt": prompt,
        "n": 1,
        "size": size_for_openai(size),
        "response_format": "b64_json",
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    logger.info("openai images/generations POST %s model=%s", url, model_name)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException as exc:
        raise ServiceUnavailableError("文生图请求超时，请稍后重试") from exc
    except httpx.HTTPError as exc:
        raise ServiceUnavailableError(f"文生图网络错误：{exc}") from exc

    if resp.status_code >= 400:
        detail = _safe_error_detail(resp)
        if resp.status_code in (400, 404, 422) and "response_format" in detail.lower():
            payload.pop("response_format", None)
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.post(url, json=payload, headers=headers)
            except httpx.HTTPError as exc:
                raise ServiceUnavailableError(f"文生图网络错误：{exc}") from exc
            if resp.status_code >= 400:
                raise ServiceUnavailableError(
                    _format_http_error(resp.status_code, _safe_error_detail(resp))
                )
        else:
            raise ServiceUnavailableError(_format_http_error(resp.status_code, detail))

    try:
        data = resp.json()
    except Exception as exc:
        raise ServiceUnavailableError("文生图返回无法解析的 JSON") from exc

    items = data.get("data") if isinstance(data, dict) else None
    if not isinstance(items, list) or not items:
        raise ServiceUnavailableError("文生图未返回图片数据")

    first = items[0] if isinstance(items[0], dict) else {}
    b64 = first.get("b64_json") or first.get("b64")
    if isinstance(b64, str) and b64.strip():
        try:
            raw = base64.b64decode(b64)
        except Exception as exc:
            raise ServiceUnavailableError("文生图 base64 解码失败") from exc
        return raw, _sniff_content_type(raw)

    image_url = first.get("url")
    if isinstance(image_url, str) and image_url.startswith(("http://", "https://")):
        return await _download_image(image_url, timeout=timeout)

    raise ServiceUnavailableError("文生图响应缺少 b64_json / url")


async def _download_image(image_url: str, *, timeout: float) -> tuple[bytes, str]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            img_resp = await client.get(image_url)
        img_resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise ServiceUnavailableError(f"下载生成图片失败：{exc}") from exc
    raw = img_resp.content
    ct = (img_resp.headers.get("content-type") or "").split(";")[0].strip()
    if not ct or ct == "application/octet-stream":
        ct = _sniff_content_type(raw)
    return raw, ct


def _safe_error_detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        if isinstance(body, dict):
            base_resp = body.get("base_resp")
            if isinstance(base_resp, dict) and base_resp.get("status_msg"):
                return str(base_resp["status_msg"])[:400]
            err = body.get("error")
            if isinstance(err, dict) and err.get("message"):
                return str(err["message"])[:400]
            if body.get("message"):
                return str(body["message"])[:400]
            return str(body)[:400]
    except Exception:
        pass
    return (resp.text or "")[:400]


def _sniff_content_type(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"
