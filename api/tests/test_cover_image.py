"""Image cover generation (mocked) + cover_url helpers."""
from __future__ import annotations

import pytest

from app.core.errors import BadRequestError, ServiceUnavailableError
from app.services import cover_generate as cover_svc
from app.services import cover_settings as cover_cfg
from app.services.cover_url import (
    expand_cover_url,
    normalize_cover_url,
    put_cover_image,
    storage_key_from_cover,
)
from app.storage import reset_storage_singleton


def test_normalize_and_expand_roundtrip(tmp_path, monkeypatch):
    from app.core import config as cfg
    from app.storage import LocalFsStorage
    import app.storage as storage_mod

    reset_storage_singleton()
    storage_mod._singleton = LocalFsStorage(root=tmp_path, signed_token_secret="test")
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    stored = put_cover_image(data=png, content_type="image/png")
    assert stored.startswith("storage:")
    key = stored.removeprefix("storage:")
    expanded = expand_cover_url(stored)
    assert expanded and expanded.startswith("/api/storage/")
    assert key in expanded
    assert normalize_cover_url(expanded) == stored
    assert storage_key_from_cover(expanded) == key
    assert normalize_cover_url("gen:v3:accent:food:orbs:111111:222222:333333:444444:555555").startswith(
        "gen:v3:"
    )
    reset_storage_singleton()


@pytest.mark.asyncio
async def test_generate_cover_image_mode(db_session, monkeypatch, tmp_path):
    from app.storage import LocalFsStorage
    import app.storage as storage_mod

    reset_storage_singleton()
    storage_mod._singleton = LocalFsStorage(root=tmp_path, signed_token_secret="test")

    row = await cover_cfg.get_cover_settings_row(db_session)
    row.image_prompt_system = "SYS_IMG"
    row.image_prompt_user = "T={title};D={description}"
    row.image_size = "512x768"
    db_session.add(row)
    await db_session.commit()

    async def fake_llm(_session):
        class L:
            provider = "openai"
            api_key = "k"
            base_url = "https://example.com/v1"
            model_name = "flux"
            params_json = None

        return L()

    async def fake_bytes(**kwargs):
        assert "美食" in kwargs["prompt"]
        assert "探店" in kwargs["prompt"]
        assert kwargs["model_name"] == "flux"
        assert kwargs["size"] == "512x768"
        return b"\x89PNG\r\n\x1a\n" + b"\x01" * 16, "image/png"

    monkeypatch.setattr(cover_svc, "get_active_cover_image_llm", fake_llm)
    monkeypatch.setattr(cover_svc, "generate_image_bytes", fake_bytes)

    result = await cover_svc.generate_cover(
        db_session, title="美食探店", description="周末探店笔记"
    )
    assert result["layout"] == "image"
    assert result["cover_url"].startswith("/api/storage/")
    assert "token=" in result["cover_url"]
    reset_storage_singleton()


@pytest.mark.asyncio
async def test_generate_cover_image_missing_role(db_session, monkeypatch):
    row = await cover_cfg.get_cover_settings_row(db_session)
    db_session.add(row)
    await db_session.commit()

    from app.core.errors import NotFoundError

    async def missing(_session):
        raise NotFoundError("role=cover_image 没有默认模型（请在 admin 配置）")

    monkeypatch.setattr(cover_svc, "get_active_cover_image_llm", missing)

    with pytest.raises(BadRequestError) as ei:
        await cover_svc.generate_cover(db_session, title="测试")
    assert "cover_image" in ei.value.message or "文生图" in ei.value.message


@pytest.mark.asyncio
async def test_generate_cover_image_provider_error(db_session, monkeypatch):
    row = await cover_cfg.get_cover_settings_row(db_session)
    db_session.add(row)
    await db_session.commit()

    async def fake_llm(_session):
        class L:
            provider = "openai"
            api_key = "k"
            base_url = "https://example.com/v1"
            model_name = "flux"
            params_json = None

        return L()

    async def boom(**_k):
        raise ServiceUnavailableError("文生图失败（HTTP 401）：bad key")

    monkeypatch.setattr(cover_svc, "get_active_cover_image_llm", fake_llm)
    monkeypatch.setattr(cover_svc, "generate_image_bytes", boom)

    with pytest.raises(ServiceUnavailableError) as ei:
        await cover_svc.generate_cover(db_session, title="测试")
    assert "401" in ei.value.message or "文生图" in ei.value.message
