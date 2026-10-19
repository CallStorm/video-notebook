"""聚合搜索：鉴权、聚合与单平台失败降级。"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.user import User
from app.schemas.search import PlatformSearchError, SearchResultItem

pytestmark = pytest.mark.asyncio


async def _user(db_session, phone: str = "13900001111") -> str:
    u = User(phone=phone, name=phone, role="user", status="active")
    u.set_password("userpw1234")
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    token, _ = create_access_token(u.id, role="user")
    return token


async def test_search_requires_auth(client: AsyncClient) -> None:
    resp = await client.post("/api/search", json={"query": "test"})
    assert resp.status_code == 401


async def test_search_aggregates_and_keeps_platform_errors(
    client: AsyncClient, db_session
) -> None:
    token = await _user(db_session)

    yt = [
        SearchResultItem(
            id="abc",
            title="YT clip",
            url="https://www.youtube.com/watch?v=abc",
            platform="youtube",
            duration=12,
            uploader="u",
            view_count=10,
        )
    ]
    bili = [
        SearchResultItem(
            id="BVxxx",
            title="Bili clip",
            url="https://www.bilibili.com/video/BVxxx",
            platform="bilibili",
        )
    ]

    async def fake_one(platform, query, limit):
        if platform == "youtube":
            return yt
        if platform == "bilibili":
            return bili
        return PlatformSearchError(platform="douyin", message="抖音搜索失败: blocked")

    with patch("app.search.service._search_one", side_effect=fake_one):
        resp = await client.post(
            "/api/search",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": "notebooklm", "platforms": ["youtube", "bilibili", "douyin"]},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["items"]) == 2
    platforms = {i["platform"] for i in body["items"]}
    assert platforms == {"youtube", "bilibili"}
    assert body["errors"] == [{"platform": "douyin", "message": "抖音搜索失败: blocked"}]


async def test_search_empty_query_rejected(client: AsyncClient, db_session) -> None:
    token = await _user(db_session, phone="13900001112")
    resp = await client.post(
        "/api/search",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "  "},
    )
    assert resp.status_code == 422
