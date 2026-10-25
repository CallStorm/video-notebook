"""Admin cover settings + generate_cover config / error paths."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.errors import ServiceUnavailableError
from app.core.security import create_access_token
from app.cover_settings.defaults import (
    DEFAULT_COVER_SYSTEM_PROMPT,
    DEFAULT_COVER_USER_PROMPT,
    DEFAULT_COVER_TEMPERATURE,
)
from app.models.user import User
from app.services import cover_generate as cover_svc
from app.services import cover_settings as cover_cfg


async def _admin(db_session) -> tuple[User, str]:
    u = User(phone="13800000141", name="admin-cover", role="admin", status="active")
    u.set_password("adminpw1234")
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    token, _ = create_access_token(u.id, role="admin")
    return u, token


@pytest.mark.asyncio
async def test_cover_settings_get_put_and_reset(client: AsyncClient, db_session):
    _u, token = await _admin(db_session)
    h = {"Authorization": f"Bearer {token}"}

    r = await client.get("/api/admin/cover-settings", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_custom_system"] is False
    assert body["is_custom_user"] is False
    assert body["prompt_system"] == DEFAULT_COVER_SYSTEM_PROMPT
    assert body["prompt_user"] == DEFAULT_COVER_USER_PROMPT
    assert body["temperature"] == DEFAULT_COVER_TEMPERATURE
    assert body["force_keyword_motif"] is True
    assert body["fallback_on_error"] is False
    assert body["mode"] == "image"
    assert "image_prompt_system" in body
    assert body["image_size"] == "512x768"

    r2 = await client.put(
        "/api/admin/cover-settings",
        headers=h,
        json={
            "prompt_system": "只输出 JSON。",
            "prompt_user": "名称：{title}\n描述：{description}",
            "temperature": 0.4,
            "force_keyword_motif": False,
            "fallback_on_error": True,
        },
    )
    assert r2.status_code == 200, r2.text
    b2 = r2.json()
    assert b2["is_custom_system"] is True
    assert b2["is_custom_user"] is True
    assert b2["prompt_system"] == "只输出 JSON。"
    assert b2["prompt_user"] == "名称：{title}\n描述：{description}"
    assert b2["temperature"] == 0.4
    assert b2["force_keyword_motif"] is False
    assert b2["fallback_on_error"] is True

    r3 = await client.put(
        "/api/admin/cover-settings",
        headers=h,
        json={
            "prompt_system": "  ",
            "prompt_user": "",
            "temperature": 0.5,
            "force_keyword_motif": True,
            "fallback_on_error": False,
        },
    )
    assert r3.status_code == 200, r3.text
    b3 = r3.json()
    assert b3["is_custom_system"] is False
    assert b3["is_custom_user"] is False
    assert b3["prompt_system"] == DEFAULT_COVER_SYSTEM_PROMPT
    assert b3["prompt_user"] == DEFAULT_COVER_USER_PROMPT


@pytest.mark.asyncio
async def test_render_user_prompt_placeholders():
    rendered = cover_cfg.render_user_prompt(
        "T={title};D={description}",
        title="美食",
        description="探店",
    )
    assert rendered == "T=美食;D=探店"
    empty = cover_cfg.render_user_prompt(
        "T={title};D={description}",
        title="A",
        description="",
    )
    assert "（无）" in empty


@pytest.mark.asyncio
async def test_generate_cover_uses_config_and_errors_without_fallback(
    db_session, monkeypatch
):
    row = await cover_cfg.get_cover_settings_row(db_session)
    row.mode = "svg"
    row.prompt_system = "SYS_CUSTOM"
    row.prompt_user = "名称：{title}|描述：{description}"
    row.temperature = 0.42
    row.force_keyword_motif = True
    row.fallback_on_error = False
    db_session.add(row)
    await db_session.commit()

    captured: dict = {}

    class FakeProvider:
        async def complete(self, user_msg, *, system, max_tokens, temperature):
            captured["user"] = user_msg
            captured["system"] = system
            captured["temperature"] = temperature
            raise RuntimeError("llm down")

    async def fake_llm(_session):
        class L:
            provider = "openai"
            api_key = "k"
            base_url = None
            model_name = "m"
            params_json = None

        return L()

    monkeypatch.setattr(cover_svc, "get_active_logo_llm", fake_llm)
    monkeypatch.setattr(cover_svc, "make_provider", lambda **_k: FakeProvider())

    with pytest.raises(ServiceUnavailableError) as ei:
        await cover_svc.generate_cover(db_session, title="美食探店", description="周末")
    assert "封面生成失败" in ei.value.message
    assert captured["system"] == "SYS_CUSTOM"
    assert "美食探店" in captured["user"]
    assert "周末" in captured["user"]
    assert captured["temperature"] == 0.42


@pytest.mark.asyncio
async def test_generate_cover_fallback_on_error(db_session, monkeypatch):
    row = await cover_cfg.get_cover_settings_row(db_session)
    row.mode = "svg"
    row.fallback_on_error = True
    row.prompt_system = None
    row.prompt_user = None
    db_session.add(row)
    await db_session.commit()

    class FakeProvider:
        async def complete(self, *_a, **_k):
            raise RuntimeError("boom")

    async def fake_llm(_session):
        class L:
            provider = "openai"
            api_key = "k"
            base_url = None
            model_name = "m"
            params_json = None

        return L()

    monkeypatch.setattr(cover_svc, "get_active_logo_llm", fake_llm)
    monkeypatch.setattr(cover_svc, "make_provider", lambda **_k: FakeProvider())

    result = await cover_svc.generate_cover(db_session, title="美食探店")
    assert result["cover_url"].startswith("gen:v3:")
    assert result["motif"] == "food"


@pytest.mark.asyncio
async def test_generate_cover_rejects_unparseable_without_fallback(
    db_session, monkeypatch
):
    row = await cover_cfg.get_cover_settings_row(db_session)
    row.mode = "svg"
    row.fallback_on_error = False
    db_session.add(row)
    await db_session.commit()

    class FakeProvider:
        async def complete(self, *_a, **_k):
            return "这不是 JSON"

    async def fake_llm(_session):
        class L:
            provider = "openai"
            api_key = "k"
            base_url = None
            model_name = "m"
            params_json = None

        return L()

    monkeypatch.setattr(cover_svc, "get_active_logo_llm", fake_llm)
    monkeypatch.setattr(cover_svc, "make_provider", lambda **_k: FakeProvider())

    with pytest.raises(ServiceUnavailableError) as ei:
        await cover_svc.generate_cover(db_session, title="随便")
    assert "无法解析" in ei.value.message
