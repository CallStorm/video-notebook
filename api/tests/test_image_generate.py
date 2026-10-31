"""Unit tests for image_generate URL normalize + MiniMax/OpenAI routing."""
from __future__ import annotations

import base64
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.errors import BadRequestError, ServiceUnavailableError
from app.llm import image_generate as ig
from app.llm.image_generate import (
    generate_image_bytes,
    is_minimax_image,
    minimax_image_generation_url,
    minimax_size_payload,
    openai_images_base_url,
    openai_images_generations_url,
    size_for_openai,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://api.openai.com/v1", "https://api.openai.com/v1"),
        ("https://api.openai.com/v1/", "https://api.openai.com/v1"),
        ("https://api.openai.com", "https://api.openai.com/v1"),
        (
            "https://api.siliconflow.cn/v1/chat/completions",
            "https://api.siliconflow.cn/v1",
        ),
        (
            "https://api.siliconflow.cn/v1/images/generations",
            "https://api.siliconflow.cn/v1",
        ),
    ],
)
def test_openai_images_base_url_normalize(raw, expected):
    assert openai_images_base_url(raw) == expected
    assert openai_images_generations_url(raw) == f"{expected}/images/generations"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://api.minimax.cn/v1", "https://api.minimax.cn/v1/image_generation"),
        ("https://api.minimax.io", "https://api.minimax.io/v1/image_generation"),
        (
            "https://api.minimaxi.com/v1",
            "https://api.minimaxi.com/v1/image_generation",
        ),
        (
            "https://api.minimaxi.com/anthropic",
            "https://api.minimaxi.com/v1/image_generation",
        ),
        (
            "https://api.minimaxi.com/v1/chat/completions",
            "https://api.minimaxi.com/v1/image_generation",
        ),
    ],
)
def test_minimax_image_url(raw, expected):
    assert minimax_image_generation_url(raw) == expected


def test_is_minimax_detection():
    assert is_minimax_image(base_url="https://api.minimaxi.com/v1", model_name="x")
    assert is_minimax_image(base_url=None, model_name="image-01")
    assert is_minimax_image(base_url=None, model_name="m", provider="minimax")
    assert not is_minimax_image(
        base_url="https://api.siliconflow.cn/v1", model_name="flux", provider="openai"
    )


def test_size_helpers():
    assert minimax_size_payload("3:4") == {"aspect_ratio": "3:4"}
    assert minimax_size_payload("512x768") == {"width": 512, "height": 768}
    assert size_for_openai("3:4") == "768x1024"
    assert size_for_openai("512x768") == "512x768"


def _mock_response(status: int, json_body: dict[str, Any] | None = None, text: str = ""):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.text = text
    if json_body is not None:
        resp.json.return_value = json_body
    else:
        resp.json.side_effect = ValueError("no json")
    return resp


@pytest.mark.asyncio
async def test_minimax_generate_base64():
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    posted: dict[str, Any] = {}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            posted["url"] = url
            posted["json"] = json
            return _mock_response(
                200,
                {
                    "base_resp": {"status_code": 0, "status_msg": "success"},
                    "data": {"image_base64": [base64.b64encode(png).decode()]},
                },
            )

    with patch.object(ig.httpx, "AsyncClient", FakeClient):
        raw, ct = await generate_image_bytes(
            api_key="k",
            base_url="https://api.minimaxi.com/v1",
            model_name="image-01",
            prompt="a notebook cover about cooking",
            size="512x768",
            provider="minimax",
        )
    assert posted["url"] == "https://api.minimaxi.com/v1/image_generation"
    assert posted["json"]["model"] == "image-01"
    assert posted["json"]["response_format"] == "base64"
    assert posted["json"]["width"] == 512
    assert posted["json"]["height"] == 768
    assert raw.startswith(b"\x89PNG")
    assert ct == "image/png"


@pytest.mark.asyncio
async def test_minimax_rejects_chat_model():
    with pytest.raises(BadRequestError) as ei:
        await generate_image_bytes(
            api_key="k",
            base_url="https://api.minimaxi.com/v1",
            model_name="MiniMax-M3",
            prompt="x",
            provider="minimax",
        )
    assert "image-01" in ei.value.message


@pytest.mark.asyncio
async def test_openai_404_message():
    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            return _mock_response(404, text="404 page not found")

    with patch.object(ig.httpx, "AsyncClient", FakeClient):
        with pytest.raises(ServiceUnavailableError) as ei:
            await generate_image_bytes(
                api_key="k",
                base_url="https://api.siliconflow.cn/v1",
                model_name="flux",
                prompt="x",
                provider="openai",
            )
    assert "404" in ei.value.message
    assert "images/generations" in ei.value.message or "出图" in ei.value.message
