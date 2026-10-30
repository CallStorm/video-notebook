"""Admin cover settings + image cover generate config paths."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.cover_settings.defaults import (
    DEFAULT_IMAGE_COVER_SYSTEM_PROMPT,
    DEFAULT_IMAGE_COVER_USER_PROMPT,
    DEFAULT_IMAGE_COVER_SIZE,
)
from app.models.user import User
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
    assert body["is_custom_image_system"] is False
    assert body["is_custom_image_user"] is False
    assert body["image_prompt_system"] == DEFAULT_IMAGE_COVER_SYSTEM_PROMPT
    assert body["image_prompt_user"] == DEFAULT_IMAGE_COVER_USER_PROMPT
    assert body["image_size"] == DEFAULT_IMAGE_COVER_SIZE
    assert "mode" not in body
    assert "prompt_system" not in body
    assert "force_keyword_motif" not in body

    r2 = await client.put(
        "/api/admin/cover-settings",
        headers=h,
        json={
            "image_prompt_system": "SYS_IMG_CUSTOM",
            "image_prompt_user": "T={title};D={description}",
            "image_size": "512x768",
        },
    )
    assert r2.status_code == 200, r2.text
    b2 = r2.json()
    assert b2["is_custom_image_system"] is True
    assert b2["is_custom_image_user"] is True
    assert b2["image_prompt_system"] == "SYS_IMG_CUSTOM"
    assert b2["image_prompt_user"] == "T={title};D={description}"
    assert b2["image_size"] == "512x768"

    r3 = await client.put(
        "/api/admin/cover-settings",
        headers=h,
        json={
            "image_prompt_system": "  ",
            "image_prompt_user": "",
            "image_size": "512x768",
        },
    )
    assert r3.status_code == 200, r3.text
    b3 = r3.json()
    assert b3["is_custom_image_system"] is False
    assert b3["is_custom_image_user"] is False
    assert b3["image_prompt_system"] == DEFAULT_IMAGE_COVER_SYSTEM_PROMPT
    assert b3["image_prompt_user"] == DEFAULT_IMAGE_COVER_USER_PROMPT


@pytest.mark.asyncio
async def test_render_image_prompt_placeholders():
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

    combined = cover_cfg.render_image_prompt(
        "SYS",
        "T={title};D={description}",
        title="X",
        description="Y",
    )
    assert combined.startswith("SYS")
    assert "T=X;D=Y" in combined
