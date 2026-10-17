"""基础存活检查。"""
from __future__ import annotations

from httpx import AsyncClient


async def test_health_returns_ok(client: AsyncClient) -> None:
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_root_says_service_name(client: AsyncClient) -> None:
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "service" in resp.json()
