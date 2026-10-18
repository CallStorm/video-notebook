"""AI emoji icon generation."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.services.icon_generate import extract_emoji


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("🎬", "🎬"),
        ("  📚  ", "📚"),
        ("推荐：🚀", "🚀"),
        ("只用这个 🎓 就好", "🎓"),
        ("", None),
        ("hello", None),
        ("abc123", None),
    ],
)
def test_extract_emoji(raw: str, expected: str | None):
    assert extract_emoji(raw) == expected


async def test_list_default_models_includes_logo(client: AsyncClient, db_session):
    from app.models.user import User

    admin = User(phone="13900008888", name="LogoAdmin", role="admin", status="active")
    admin.set_password("adminpw1234")
    db_session.add(admin)
    await db_session.commit()

    login = await client.post(
        "/api/auth/login",
        json={"phone": "13900008888", "password": "adminpw1234"},
    )
    assert login.status_code == 200
    token = login.json()["access"]

    resp = await client.get(
        "/api/admin/default-models",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    roles = {d["role"] for d in resp.json()}
    assert "logo" in roles
    assert roles >= {"chat", "tts", "stt", "logo"}


async def test_generate_icon_endpoint(client: AsyncClient, db_session):
    from app.models.user import User

    user = User(phone="13900007777", name="IconUser", role="user", status="active")
    user.set_password("password123")
    db_session.add(user)
    await db_session.commit()

    login = await client.post(
        "/api/auth/login",
        json={"phone": "13900007777", "password": "password123"},
    )
    assert login.status_code == 200
    token = login.json()["access"]

    with patch(
        "app.services.icon_generate.get_active_logo_llm",
        new=AsyncMock(
            return_value=type(
                "L",
                (),
                {
                    "provider": "minimax",
                    "api_key": "sk",
                    "base_url": None,
                    "model_name": "m",
                    "params_json": None,
                },
            )()
        ),
    ), patch("app.services.icon_generate.make_provider") as make:
        provider = AsyncMock()
        provider.complete = AsyncMock(return_value="🎬")
        make.return_value = provider

        resp = await client.post(
            "/api/icons/generate",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "电影笔记"},
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["icon"] == "🎬"


async def test_generate_icon_rejects_empty_name(client: AsyncClient, db_session):
    from app.models.user import User

    user = User(phone="13900006666", name="IconUser2", role="user", status="active")
    user.set_password("password123")
    db_session.add(user)
    await db_session.commit()

    login = await client.post(
        "/api/auth/login",
        json={"phone": "13900006666", "password": "password123"},
    )
    token = login.json()["access"]

    resp = await client.post(
        "/api/icons/generate",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "   "},
    )
    assert resp.status_code == 400
